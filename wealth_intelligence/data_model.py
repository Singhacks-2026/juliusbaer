"""Phase 0 — the foundation every detector builds on.

Loads the 12 source files into one joined, currency-aware model. Twenty clients
is small; we hold the whole book in memory and index it the way the detectors
need it. No pandas — the standard library is enough and keeps the engine
portable into environments where a bank will not let you `pip install`.

Design decisions grounded in docs/DATA_DICTIONARY.md:

* ``holdings.market_value_usd`` is the source of truth for position value at
  every snapshot. We never derive USD value from the ``aum_<date>`` columns in
  portfolios.csv, because those are in each portfolio's *base* currency while
  only ``aum_usd_current`` is USD — comparing them reads a currency conversion
  as a gain or loss (CL-0014's HKD book "falling" 206m -> 26m is the trap).
* Loan-to-value is ``drawn / lending_value`` where lending value is already
  advance-rate haircut. We read the provided per-snapshot LTV rather than
  recomputing it.
* Custody accounts are part of the wealth picture but are *not* measured against
  a mandate. The model records ``service_model`` so detectors can honour that.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, os.pardir, "data"))

SNAPSHOTS = [
    "2025-12-31",
    "2026-02-27",
    "2026-03-31",
    "2026-06-30",
    "2026-08-26",
]
TODAY = SNAPSHOTS[-1]
BASELINE = SNAPSHOTS[0]


# --------------------------------------------------------------------------- #
# Low-level loading
# --------------------------------------------------------------------------- #
def _read_csv(name: str) -> list[dict[str, str]]:
    path = os.path.join(DATA_DIR, name)
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _read_json(name: str) -> Any:
    path = os.path.join(DATA_DIR, name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _num(value: Any) -> Optional[float]:
    """Parse a numeric cell. Blank / None / unparseable -> None (not 0.0).

    The distinction matters: a missing advance rate is unknown, not zero.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in {"none", "nan", "null"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# FX — everything reduces to USD
# --------------------------------------------------------------------------- #
# How to turn one unit of <ccy> into USD, per snapshot, from market_context.csv.
# Series are quoted either as "<X> per USD" (divide) or "USD per <X>" (multiply).
_FX_SERIES = {
    "USD": None,  # identity
    "SGD": ("USDSGD", "per_usd"),
    "HKD": ("USDHKD", "per_usd"),
    "JPY": ("USDJPY", "per_usd"),
    "CHF": ("USDCHF", "per_usd"),
    "CNH": ("USDCNH", "per_usd"),
    "CNY": ("USDCNH", "per_usd"),
    "IDR": ("USDIDR", "per_usd"),
    "THB": ("USDTHB", "per_usd"),
    "INR": ("USDINR", "per_usd"),
    "EUR": ("EURUSD", "usd_per"),
    "GBP": ("GBPUSD", "usd_per"),
}


@dataclass
class FX:
    """USD conversion using the market_context rates at each snapshot."""

    # rates[snapshot][series_id] = value
    rates: dict[str, dict[str, float]]

    def to_usd(self, amount: float, ccy: str, snapshot: str = TODAY) -> float:
        ccy = (ccy or "USD").upper()
        spec = _FX_SERIES.get(ccy)
        if spec is None:
            return amount  # USD or unknown -> treat as USD, honestly flagged upstream
        series_id, direction = spec
        rate = self.rates.get(snapshot, {}).get(series_id)
        if rate is None:
            return amount
        return amount / rate if direction == "per_usd" else amount * rate

    def known(self, ccy: str) -> bool:
        return (ccy or "USD").upper() in _FX_SERIES


# --------------------------------------------------------------------------- #
# Domain records
# --------------------------------------------------------------------------- #
@dataclass
class Holding:
    snapshot_date: str
    portfolio_id: str
    client_id: str
    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str
    region: str
    instrument_ccy: str
    quantity: Optional[float]
    market_value_usd: Optional[float]
    weight_pct: Optional[float]
    unrealised_pnl_pct: Optional[float]
    liquidity_tier: str
    lending_value_base: Optional[float]
    advance_rate_pct: Optional[float]
    raw: dict[str, str]

    @property
    def mv(self) -> float:
        return self.market_value_usd or 0.0


@dataclass
class Portfolio:
    portfolio_id: str
    client_id: str
    portfolio_name: str
    mandate_code: str
    mandate_name: str
    service_model: str
    base_currency: str
    raw: dict[str, str]

    @property
    def is_managed(self) -> bool:
        # Custody accounts are not measured against a mandate (data dictionary).
        return self.service_model.strip().lower() != "custody"


@dataclass
class Facility:
    facility_id: str
    client_id: str
    collateral_portfolio_id: str
    facility_type: str
    facility_ccy: str
    margin_call_ltv_pct: float
    raw: dict[str, str]

    def ltv_series(self) -> list[tuple[str, Optional[float]]]:
        return [(d, _num(self.raw.get(f"ltv_pct_{d}"))) for d in SNAPSHOTS]

    def headroom_series(self) -> list[tuple[str, Optional[float]]]:
        return [(d, _num(self.raw.get(f"headroom_{d}"))) for d in SNAPSHOTS]

    @property
    def ltv_now(self) -> Optional[float]:
        return _num(self.raw.get(f"ltv_pct_{TODAY}"))

    @property
    def drawn_now(self) -> Optional[float]:
        return _num(self.raw.get(f"drawn_{TODAY}"))

    @property
    def distance_to_call(self) -> Optional[float]:
        """Percentage points of LTV headroom before a margin call triggers."""
        if self.ltv_now is None:
            return None
        return self.margin_call_ltv_pct - self.ltv_now


@dataclass
class Mandate:
    code: str
    name: str
    # asset_class -> (min, target, max, max_single_position)
    bands: dict[str, tuple[float, float, float, float]]
    notes: str

    @property
    def has_exclusions(self) -> bool:
        return "exclusion" in self.notes.lower()


@dataclass
class Instrument:
    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str
    region: str
    currency: str
    liquidity_tier: str
    underlying_reference: str
    sustainability_excluded: bool
    concentration_limit_applies: bool
    prices: dict[str, Optional[float]]
    raw: dict[str, str]


@dataclass
class Client:
    client_id: str
    client_name: str
    age: Optional[float]
    risk_profile: str
    risk_tolerance_score: Optional[float]
    liquidity_needs: str
    life_stage: str
    base_currency: str
    tax_domicile: str
    country_of_residence: str
    booking_centre: str
    total_aum_usd: Optional[float]
    objectives: str
    source_of_wealth: str
    raw: dict[str, str]


# --------------------------------------------------------------------------- #
# The Book — the joined, indexed model
# --------------------------------------------------------------------------- #
@dataclass
class Book:
    clients: dict[str, Client]
    portfolios: dict[str, Portfolio]
    holdings: list[Holding]
    instruments: dict[str, Instrument]
    mandates: dict[str, Mandate]
    facilities: list[Facility]
    commitments: list[dict[str, str]]
    cash_needs: list[dict[str, str]]
    events: list[dict[str, str]]
    notes: list[dict[str, Any]]
    fx: FX

    # -- indexing helpers ---------------------------------------------------- #
    _by_client_snapshot: dict[tuple[str, str], list[Holding]] = field(default_factory=dict)
    _pf_by_client: dict[str, list[str]] = field(default_factory=dict)

    def _index(self) -> None:
        for h in self.holdings:
            self._by_client_snapshot.setdefault((h.client_id, h.snapshot_date), []).append(h)
        for pf in self.portfolios.values():
            self._pf_by_client.setdefault(pf.client_id, []).append(pf.portfolio_id)

    # -- accessors ----------------------------------------------------------- #
    def client_ids(self) -> list[str]:
        return list(self.clients.keys())

    def portfolios_of(self, client_id: str) -> list[Portfolio]:
        return [self.portfolios[p] for p in self._pf_by_client.get(client_id, [])]

    def holdings_of(self, client_id: str, snapshot: str = TODAY) -> list[Holding]:
        return list(self._by_client_snapshot.get((client_id, snapshot), []))

    def total_usd(self, client_id: str, snapshot: str = TODAY) -> float:
        return sum(h.mv for h in self.holdings_of(client_id, snapshot))

    def facilities_of(self, client_id: str) -> list[Facility]:
        return [f for f in self.facilities if f.client_id == client_id]

    def notes_of(self, client_id: str) -> list[dict[str, Any]]:
        return [n for n in self.notes if n.get("client_id") == client_id]

    def cash_needs_of(self, client_id: str) -> list[dict[str, str]]:
        return [c for c in self.cash_needs if c.get("client_id") == client_id]

    def commitments_of(self, client_id: str) -> list[dict[str, str]]:
        return [c for c in self.commitments if c.get("client_id") == client_id]

    def instrument(self, instrument_id: str) -> Optional[Instrument]:
        return self.instruments.get(instrument_id)

    def mandate_for_portfolio(self, portfolio_id: str) -> Optional[Mandate]:
        pf = self.portfolios.get(portfolio_id)
        if pf is None:
            return None
        return self.mandates.get(pf.mandate_code)

    # -- Phase 0 signature helper: one client, everything joined ------------- #
    def client_360(self, client_id: str, snapshot: str = TODAY) -> dict[str, Any]:
        """Everything about a client in one dict — the substrate detectors read."""
        client = self.clients[client_id]
        holds = self.holdings_of(client_id, snapshot)
        total = sum(h.mv for h in holds)
        return {
            "client": client,
            "portfolios": self.portfolios_of(client_id),
            "holdings": holds,
            "total_usd": total,
            "facilities": self.facilities_of(client_id),
            "cash_needs": self.cash_needs_of(client_id),
            "commitments": self.commitments_of(client_id),
            "notes": self.notes_of(client_id),
        }


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #
def _load_fx(rows: list[dict[str, str]]) -> FX:
    rates: dict[str, dict[str, float]] = {}
    for r in rows:
        v = _num(r.get("value"))
        if v is None:
            continue
        rates.setdefault(r["snapshot_date"], {})[r["series_id"]] = v
    return FX(rates=rates)


def _load_mandates(rows: list[dict[str, str]]) -> dict[str, Mandate]:
    tmp: dict[str, Mandate] = {}
    for r in rows:
        code = r["mandate_code"]
        if code not in tmp:
            tmp[code] = Mandate(code=code, name=r["mandate_name"], bands={}, notes=r.get("mandate_notes", ""))
        tmp[code].bands[r["asset_class"]] = (
            _num(r["min_pct"]) or 0.0,
            _num(r["target_pct"]) or 0.0,
            _num(r["max_pct"]) or 0.0,
            _num(r["max_single_position_pct"]) or 0.0,
        )
    return tmp


def load_book(data_dir: Optional[str] = None) -> Book:
    global DATA_DIR
    if data_dir:
        DATA_DIR = data_dir

    fx = _load_fx(_read_csv("market_context.csv"))

    clients = {
        r["client_id"]: Client(
            client_id=r["client_id"],
            client_name=r["client_name"],
            age=_num(r.get("age")),
            risk_profile=r.get("risk_profile", ""),
            risk_tolerance_score=_num(r.get("risk_tolerance_score")),
            liquidity_needs=r.get("liquidity_needs", ""),
            life_stage=r.get("life_stage", ""),
            base_currency=r.get("base_currency", "USD"),
            tax_domicile=r.get("tax_domicile", ""),
            country_of_residence=r.get("country_of_residence", ""),
            booking_centre=r.get("booking_centre", ""),
            total_aum_usd=_num(r.get("total_aum_usd")),
            objectives=r.get("objectives", ""),
            source_of_wealth=r.get("source_of_wealth", ""),
            raw=r,
        )
        for r in _read_csv("clients.csv")
    }

    portfolios = {
        r["portfolio_id"]: Portfolio(
            portfolio_id=r["portfolio_id"],
            client_id=r["client_id"],
            portfolio_name=r["portfolio_name"],
            mandate_code=r.get("mandate_code", ""),
            mandate_name=r.get("mandate_name", ""),
            service_model=r.get("service_model", ""),
            base_currency=r.get("base_currency", "USD"),
            raw=r,
        )
        for r in _read_csv("portfolios.csv")
    }

    holdings = [
        Holding(
            snapshot_date=r["snapshot_date"],
            portfolio_id=r["portfolio_id"],
            client_id=r["client_id"],
            instrument_id=r["instrument_id"],
            instrument_name=r["instrument_name"],
            asset_class=r.get("asset_class", ""),
            sub_asset_class=r.get("sub_asset_class", ""),
            sector=r.get("sector", ""),
            region=r.get("region", ""),
            instrument_ccy=r.get("instrument_ccy", ""),
            quantity=_num(r.get("quantity")),
            market_value_usd=_num(r.get("market_value_usd")),
            weight_pct=_num(r.get("weight_pct")),
            unrealised_pnl_pct=_num(r.get("unrealised_pnl_pct")),
            liquidity_tier=r.get("liquidity_tier", ""),
            lending_value_base=_num(r.get("lending_value_base")),
            advance_rate_pct=_num(r.get("advance_rate_pct")),
            raw=r,
        )
        for r in _read_csv("holdings.csv")
    ]

    instruments = {
        r["instrument_id"]: Instrument(
            instrument_id=r["instrument_id"],
            instrument_name=r["instrument_name"],
            asset_class=r.get("asset_class", ""),
            sub_asset_class=r.get("sub_asset_class", ""),
            sector=r.get("sector", ""),
            region=r.get("region", ""),
            currency=r.get("currency", ""),
            liquidity_tier=r.get("liquidity_tier", ""),
            underlying_reference=r.get("underlying_reference", "") or "",
            sustainability_excluded=(r.get("sustainability_excluded", "N").strip().upper() == "Y"),
            concentration_limit_applies=(r.get("concentration_limit_applies", "N").strip().upper() == "Y"),
            prices={d: _num(r.get(f"price_{d}")) for d in SNAPSHOTS},
            raw=r,
        )
        for r in _read_csv("instruments.csv")
    }

    facilities = [
        Facility(
            facility_id=r["facility_id"],
            client_id=r["client_id"],
            collateral_portfolio_id=r.get("collateral_portfolio_id", ""),
            facility_type=r.get("facility_type", ""),
            facility_ccy=r.get("facility_ccy", ""),
            margin_call_ltv_pct=_num(r.get("margin_call_ltv_pct")) or 100.0,
            raw=r,
        )
        for r in _read_csv("credit_facilities.csv")
    ]

    book = Book(
        clients=clients,
        portfolios=portfolios,
        holdings=holdings,
        instruments=instruments,
        mandates=_load_mandates(_read_csv("mandates.csv")),
        facilities=facilities,
        commitments=_read_csv("commitments.csv"),
        cash_needs=_read_csv("planned_cash_needs.csv"),
        events=_read_csv("event_log.csv"),
        notes=_read_json("rm_notes.json"),
        fx=fx,
    )
    book._index()
    return book
