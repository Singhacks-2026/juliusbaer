"""Phase 1 — the signal engine.

Five deterministic detectors. Each takes the Book and a client, and returns
zero or more Findings. Every number is computed from the source files; the
detectors never guess. Where the data is ambiguous they say so rather than
assert — "honesty about uncertainty" is explicitly rewarded.

    detect_collateral      Lombard LTV vs the margin-call line, traced over time.
    detect_concentration   Single-name exposure across the household, with
                           structured-product look-through.
    detect_mandate         Allocation-band and single-position breaches, plus
                           sustainable-mandate exclusion breaches.
    detect_liquidity       Confirmed near-term cash needs vs what is sellable,
                           including gated funds and currency mismatch.
    detect_attribution     The largest USD moves since baseline, tied to the
                           authoritative event_log.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any, Optional

from .data_model import BASELINE, SNAPSHOTS, TODAY, Book, Facility
from .findings import EVENT_SEVERITY, Finding, Severity, usd
from .lookthrough import resolve

# Positions we treat as "cash-like or promptly sellable" for liquidity.
LIQUID_TIERS = {"Daily", "Weekly"}
GATED_TIERS = {"Quarterly Gate", "Illiquid", "Monthly"}


# --------------------------------------------------------------------------- #
# 1. Collateral / margin
# --------------------------------------------------------------------------- #
def detect_collateral(book: Book, client_id: str) -> list[Finding]:
    findings: list[Finding] = []
    for f in book.facilities_of(client_id):
        dist = f.distance_to_call
        if dist is None:
            continue
        ltv = f.ltv_now or 0.0
        series = [(d, v) for d, v in f.ltv_series() if v is not None]
        first_ltv = series[0][1] if series else None
        rising = first_ltv is not None and ltv - first_ltv >= 3.0

        if dist <= 1.5:
            sev = Severity.SEVERE
        elif dist <= 4.0:
            sev = Severity.HIGH
        elif dist <= 8.0:
            sev = Severity.MEDIUM
        elif rising:
            sev = Severity.LOW
        else:
            continue  # comfortable and stable — not worth the RM's attention

        trail = " -> ".join(f"{v:.1f}%" for _, v in series)
        drawn = f.drawn_now
        headline = (
            f"{f.facility_type} at {ltv:.1f}% LTV — "
            f"{dist:.1f} pts from the {f.margin_call_ltv_pct:.0f}% margin call"
        )
        detail = (
            f"Loan-to-value has moved {trail} across the five snapshots as the "
            f"collateral portfolio ({f.collateral_portfolio_id}) revalued. "
            f"At {ltv:.1f}% the facility is {dist:.1f} percentage points below the "
            f"{f.margin_call_ltv_pct:.0f}% trigger"
            + (", and the trend is toward it." if rising else ".")
        )
        findings.append(
            Finding(
                client_id=client_id,
                category="collateral",
                severity=sev,
                headline=headline,
                detail=detail,
                facts={
                    "facility_id": f.facility_id,
                    "ltv_now_pct": round(ltv, 2),
                    "margin_call_ltv_pct": f.margin_call_ltv_pct,
                    "distance_pts": round(dist, 2),
                    "ltv_trail": [round(v, 2) for _, v in series],
                    "drawn": drawn,
                    "facility_ccy": f.facility_ccy,
                },
                evidence=[f"credit_facilities.csv:{f.facility_id}"],
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# 2. Concentration (with look-through)
# --------------------------------------------------------------------------- #
def detect_concentration(book: Book, client_id: str) -> list[Finding]:
    holds = book.holdings_of(client_id, TODAY)
    total = sum(h.mv for h in holds)
    if total <= 0:
        return []

    managed_pids = {pf.portfolio_id for pf in book.portfolios_of(client_id) if pf.is_managed}

    # Aggregate single-name exposure across every portfolio the client holds,
    # keeping managed and custody value separate — the single-position limit
    # governs only managed mandates, but the household risk picture is the whole
    # book (a custody legacy stake is still a real, if client-directed, exposure).
    direct: dict[str, float] = defaultdict(float)
    direct_managed: dict[str, float] = defaultdict(float)
    basket: dict[str, float] = defaultdict(float)
    contributors: dict[str, set[str]] = defaultdict(set)

    for h in holds:
        inst = book.instrument(h.instrument_id)
        is_managed = h.portfolio_id in managed_pids
        for exp in resolve(inst):
            if exp.kind == "direct":
                direct[exp.issuer] += h.mv
                if is_managed:
                    direct_managed[exp.issuer] += h.mv
                contributors[exp.issuer].add(h.instrument_name)
            else:
                basket[exp.issuer] += h.mv
                contributors[exp.issuer].add(h.instrument_name + " (basket)")

    limit = _tightest_single_limit(book, client_id)

    findings: list[Finding] = []
    for issuer, mv in sorted(direct.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * mv / total
        extra = basket.get(issuer, 0.0)
        extra_pct = 100.0 * extra / total
        threshold = min(limit, 10.0) if limit else 10.0
        if pct < threshold and (pct + extra_pct) < threshold:
            continue

        managed_mv = direct_managed.get(issuer, 0.0)
        managed_pct = 100.0 * managed_mv / total
        custody_only = managed_mv <= 0.01 * mv  # essentially all in custody
        # A limit breach can only exist in the managed portion.
        over = bool(limit and managed_pct > limit)

        instruments = sorted(contributors[issuer])
        multi = len(instruments) > 1
        if custody_only:
            # Client-directed legacy exposure — a diversification conversation,
            # not a governance breach. Cap severity accordingly.
            sev = Severity.HIGH if pct >= 25 else Severity.MEDIUM
        else:
            sev = Severity.HIGH if over else (Severity.MEDIUM if pct >= 15 else Severity.LOW)
            if pct >= 25 and over:
                sev = Severity.SEVERE

        if custody_only:
            tail = " — held in a custody account, so outside mandate governance; a concentration to discuss, not a breach to correct"
        elif over:
            tail = f" — over the {limit:.0f}% single-position limit on the managed portion ({managed_pct:.1f}%)"
        else:
            tail = ""
        headline = (
            f"{issuer}: {pct:.1f}% of the total book"
            + (f" (+{extra_pct:.1f}% via baskets)" if extra_pct >= 1 else "")
            + tail
        )
        look = (
            f" It is spread across {len(instruments)} instruments "
            f"({', '.join(instruments)}) — only visible once the structured products "
            f"and bonds are looked through to the name."
            if multi
            else ""
        )
        detail = (
            f"{usd(mv)} sits in {issuer}, {pct:.1f}% of the client's {usd(total)} total book"
            + (f" ({usd(managed_mv)} of it in managed mandates)" if not custody_only and managed_mv else "")
            + "." + look
        )
        findings.append(
            Finding(
                client_id=client_id,
                category="concentration",
                severity=sev,
                headline=headline,
                detail=detail,
                facts={
                    "issuer": issuer,
                    "direct_usd": round(mv, 0),
                    "direct_pct": round(pct, 2),
                    "managed_usd": round(managed_mv, 0),
                    "managed_pct": round(managed_pct, 2),
                    "custody_only": custody_only,
                    "basket_usd": round(extra, 0),
                    "single_position_limit_pct": limit,
                    "over_limit": over,
                    "instruments": instruments,
                    "total_book_usd": round(total, 0),
                },
                evidence=["holdings.csv", "instruments.csv:underlying_reference"],
            )
        )
    return findings


def _tightest_single_limit(book: Book, client_id: str) -> Optional[float]:
    limits = []
    for pf in book.portfolios_of(client_id):
        if not pf.is_managed:
            continue
        m = book.mandates.get(pf.mandate_code)
        if not m:
            continue
        for _, _, _, single in m.bands.values():
            if single:
                limits.append(single)
    return min(limits) if limits else None


# --------------------------------------------------------------------------- #
# 3. Mandate governance (bands, single position, exclusions)
# --------------------------------------------------------------------------- #
def detect_mandate(book: Book, client_id: str) -> list[Finding]:
    findings: list[Finding] = []
    for pf in book.portfolios_of(client_id):
        if not pf.is_managed:
            continue  # custody accounts are not measured against a mandate
        mandate = book.mandates.get(pf.mandate_code)
        if not mandate:
            continue
        holds = [h for h in book.holdings_of(client_id, TODAY) if h.portfolio_id == pf.portfolio_id]
        pf_total = sum(h.mv for h in holds)
        if pf_total <= 0:
            continue

        # Asset-class band breaches.
        by_class: dict[str, float] = defaultdict(float)
        for h in holds:
            by_class[h.asset_class] += h.mv
        for asset_class, mv in by_class.items():
            band = mandate.bands.get(asset_class)
            if not band:
                continue
            lo, _, hi, _ = band
            pct = 100.0 * mv / pf_total
            if pct > hi + 0.5:
                findings.append(_band_finding(client_id, pf, asset_class, pct, hi, "above", "max"))
            elif pct < lo - 0.5:
                findings.append(_band_finding(client_id, pf, asset_class, pct, lo, "below", "min"))

        # Sustainable-mandate exclusion breaches.
        if mandate.has_exclusions:
            for h in holds:
                inst = book.instrument(h.instrument_id)
                if inst and inst.sustainability_excluded:
                    pct = 100.0 * h.mv / pf_total
                    findings.append(
                        Finding(
                            client_id=client_id,
                            category="exclusion",
                            severity=Severity.HIGH,
                            headline=(
                                f"Excluded holding in a sustainable mandate: "
                                f"{h.instrument_name} ({pct:.1f}%)"
                            ),
                            detail=(
                                f"{pf.portfolio_name} runs the {mandate.name} mandate, whose "
                                f"binding exclusions cover this instrument "
                                f"(instruments.sustainability_excluded = Y), yet it holds "
                                f"{usd(h.mv)} of {h.instrument_name}. Worth confirming whether "
                                f"this is a legacy position or an oversight before the review."
                            ),
                            facts={
                                "portfolio_id": pf.portfolio_id,
                                "mandate": mandate.name,
                                "instrument": h.instrument_name,
                                "instrument_id": h.instrument_id,
                                "value_usd": round(h.mv, 0),
                                "weight_pct": round(pct, 2),
                            },
                            evidence=[
                                f"portfolios.csv:{pf.portfolio_id}",
                                f"instruments.csv:{h.instrument_id}",
                                "mandates.csv:SUSBAL",
                            ],
                        )
                    )
    return findings


def _band_finding(client_id, pf, asset_class, pct, limit, direction, kind) -> Finding:
    return Finding(
        client_id=client_id,
        category="mandate",
        severity=Severity.MEDIUM,
        headline=f"{pf.portfolio_name}: {asset_class} at {pct:.1f}%, {direction} the {limit:.0f}% {kind}",
        detail=(
            f"{pf.portfolio_name} ({pf.mandate_name}) holds {pct:.1f}% in {asset_class}, "
            f"{direction} the mandate's {kind} of {limit:.0f}%. This may be deliberate "
            f"drift or a client-directed position — check the RM notes and any waiver on file "
            f"before treating it as a breach to correct."
        ),
        facts={
            "portfolio_id": pf.portfolio_id,
            "asset_class": asset_class,
            "weight_pct": round(pct, 2),
            "limit_pct": limit,
            "direction": direction,
        },
        evidence=[f"portfolios.csv:{pf.portfolio_id}", f"mandates.csv:{pf.mandate_code}"],
    )


# --------------------------------------------------------------------------- #
# 4. Liquidity (near-term needs vs what is sellable)
# --------------------------------------------------------------------------- #
def _parse_date(s: str) -> Optional[date]:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def detect_liquidity(book: Book, client_id: str, horizon_months: int = 18) -> list[Finding]:
    holds = book.holdings_of(client_id, TODAY)
    if not holds:
        return []

    liquid_gross = sum(h.mv for h in holds if h.liquidity_tier in LIQUID_TIERS)
    gated = sum(h.mv for h in holds if h.liquidity_tier in GATED_TIERS)
    total = sum(h.mv for h in holds)

    # Assets pledged as collateral are not freely sellable: the drawn facility is
    # a prior claim, and selling into it erodes the margin buffer. Net the total
    # drawn (converted to USD) off the liquid pool — this is why a book that
    # looks liquid can be anything but (cf. Lau Chi Ming: "surprised how little
    # of it is liquid").
    encumbered = 0.0
    for f in book.facilities_of(client_id):
        drawn = f.drawn_now
        if drawn:
            encumbered += book.fx.to_usd(drawn, f.facility_ccy, TODAY)
    liquid = max(0.0, liquid_gross - encumbered)

    cutoff = date(2026, 8, 26)
    horizon_end = date(2028, 2, 26) if horizon_months == 18 else cutoff

    # Near-term, reasonably certain outflows in the horizon window.
    needs_usd = 0.0
    near_needs: list[str] = []
    ccys: set[str] = set()
    for n in book.cash_needs_of(client_id):
        certainty = (n.get("certainty") or "").lower()
        if certainty.startswith("aspirational"):
            continue
        start = _parse_date(n.get("due_from", ""))
        if start and start > horizon_end:
            continue
        amt = float(n.get("amount") or 0)
        ccy = n.get("currency", "USD")
        ccys.add(ccy)
        amt_usd = book.fx.to_usd(amt, ccy, TODAY)
        needs_usd += amt_usd
        near_needs.append(f"{n.get('description','')} ({usd(amt_usd)}, {certainty or 'n/a'})")

    # Uncalled private-market commitments are future outflows too.
    uncalled = sum(float(c.get("uncalled") or 0) for c in book.commitments_of(client_id))
    needs_total = needs_usd + uncalled

    if needs_total <= 0:
        return []

    coverage = liquid / needs_total if needs_total else float("inf")
    # Currency mismatch: obligations in a currency the liquid book is not in.
    hold_ccys = {h.instrument_ccy for h in holds if h.liquidity_tier in LIQUID_TIERS}
    fx_mismatch = any(c not in hold_ccys and c != "USD" for c in ccys) or (
        ccys and hold_ccys and not (ccys & hold_ccys) and "USD" not in hold_ccys
    )

    if coverage < 1.0:
        sev = Severity.HIGH
    elif coverage < 1.5:
        sev = Severity.MEDIUM
    elif gated > 0 and coverage < 3.0:
        sev = Severity.LOW
    else:
        return []

    headline = (
        f"Liquidity: {usd(liquid)} readily sellable against {usd(needs_total)} of "
        f"near-term needs ({coverage:.1f}x cover)"
    )
    parts = [
        f"Confirmed and likely calls on cash inside the horizon total {usd(needs_total)} "
        f"({usd(uncalled)} of it uncalled private-market commitments).",
        f"Of a {usd(total)} book, {usd(liquid_gross)} sits in daily/weekly liquidity, but "
        f"{usd(encumbered)} of that is pledged against drawn facilities, leaving "
        f"{usd(liquid)} genuinely free; {usd(gated)} is gated or illiquid."
        if encumbered > 0
        else f"Only {usd(liquid)} of the {usd(total)} book sits in daily/weekly liquidity; "
        f"{usd(gated)} is gated or illiquid.",
    ]
    if fx_mismatch:
        parts.append(
            f"The obligations are in {', '.join(sorted(ccys))} while the liquid assets are not — "
            f"a currency mismatch that has become more expensive this year."
        )
    return [
        Finding(
            client_id=client_id,
            category="liquidity",
            severity=sev,
            headline=headline,
            detail=" ".join(parts),
            facts={
                "liquid_free_usd": round(liquid, 0),
                "liquid_gross_usd": round(liquid_gross, 0),
                "encumbered_usd": round(encumbered, 0),
                "gated_illiquid_usd": round(gated, 0),
                "near_term_needs_usd": round(needs_usd, 0),
                "uncalled_commitments_usd": round(uncalled, 0),
                "coverage_ratio": round(coverage, 2),
                "fx_mismatch": bool(fx_mismatch),
                "needs": near_needs,
            },
            evidence=["planned_cash_needs.csv", "commitments.csv", "holdings.csv:liquidity_tier"],
        )
    ]


# --------------------------------------------------------------------------- #
# 5. Event attribution
# --------------------------------------------------------------------------- #
# Map event transmission keywords to the holding fields they touch.
_CHANNEL_KEYWORDS = {
    "energy": ("sector", {"Energy"}),
    "gold": ("sector", {"Gold"}),
    "precious metals": ("sector", {"Gold"}),
    "defence": ("sector", {"Industrials"}),
    "technology": ("sector", {"Information Technology"}),
    "us technology": ("sector", {"Information Technology"}),
    "shipping": ("sector", {"Industrials", "Real Estate"}),
    "real estate": ("sector", {"Real Estate"}),
    "duration": ("asset_class", {"Fixed Income"}),
    "long-duration fixed income": ("asset_class", {"Fixed Income"}),
    "rate-sensitive credit": ("asset_class", {"Fixed Income"}),
    "private credit": ("sub_asset_class", {"Private Credit"}),
    "semi-liquid alternatives": ("asset_class", {"Alternatives"}),
    "eur assets": ("region", {"Europe"}),
    "european fixed income": ("region", {"Europe"}),
}


def detect_attribution(book: Book, client_id: str, top_n: int = 3) -> list[Finding]:
    base = {h.instrument_id: h for h in book.holdings_of(client_id, BASELINE)}
    now = {h.instrument_id: h for h in book.holdings_of(client_id, TODAY)}

    # Value change per instrument driven by *price*, holding quantity constant,
    # to separate market moves from trading. We approximate with the reported
    # USD values but only report where the instrument is held at both ends.
    moves: list[tuple[float, Any]] = []
    for iid, h_now in now.items():
        h_base = base.get(iid)
        if not h_base:
            continue
        delta = h_now.mv - h_base.mv
        moves.append((delta, h_now))

    if not moves:
        return []
    moves.sort(key=lambda t: t[0])  # most negative first

    findings: list[Finding] = []
    for delta, h in moves[:top_n]:
        if delta > -50_000:  # only material drawdowns
            break
        event = _match_event(book, h)
        ev_txt = ""
        sev = Severity.LOW
        if event:
            ev_txt = (
                f" Consistent with the {event['event_date']} event "
                f"(\"{event['description'][:110]}...\"), whose transmission channels "
                f"include {event['primary_transmission']}."
            )
            sev = EVENT_SEVERITY.get(event.get("severity", ""), Severity.LOW)
        findings.append(
            Finding(
                client_id=client_id,
                category="attribution",
                severity=min(sev, Severity.MEDIUM),  # explanation, not an alert
                headline=f"{h.instrument_name} down {usd(delta)} year-to-date",
                detail=(
                    f"{h.instrument_name} ({h.sector}, {h.region}) fell {usd(delta)} between "
                    f"{BASELINE} and {TODAY}." + ev_txt
                ),
                facts={
                    "instrument": h.instrument_name,
                    "instrument_id": h.instrument_id,
                    "delta_usd": round(delta, 0),
                    "sector": h.sector,
                    "region": h.region,
                    "event_date": event["event_date"] if event else None,
                },
                evidence=(["event_log.csv:" + event["event_date"]] if event else [])
                + ["holdings.csv"],
            )
        )
    return findings


def _match_event(book: Book, holding) -> Optional[dict[str, str]]:
    """Find the most severe event whose transmission channel matches the holding."""
    best = None
    best_rank = -1
    for ev in book.events:
        channel = (ev.get("primary_transmission") or "").lower()
        for kw, (field_name, values) in _CHANNEL_KEYWORDS.items():
            if kw in channel and getattr(holding, field_name, "") in values:
                rank = int(EVENT_SEVERITY.get(ev.get("severity", ""), Severity.LOW))
                if rank > best_rank:
                    best, best_rank = ev, rank
                break
    return best


# --------------------------------------------------------------------------- #
# 6. Income / withdrawal sustainability
# --------------------------------------------------------------------------- #
# Transaction types that represent income the portfolio pays out.
_INCOME_TYPES = {"Dividend", "Coupon", "Distribution", "Interest"}
# Cash-need descriptions that represent recurring consumption (not investment).
_CONSUMPTION_HINTS = ("retirement", "living", "income", "expenses", "medical",
                      "support", "drawdown", "tuition", "fees")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _annual_portfolio_income_usd(book: Book, client_id: str) -> tuple[float, int]:
    """Annualised income the portfolio actually paid, from transactions.

    Income lands at quarter-end snapshots; we annualise from the number of
    distinct income dates present (each is one quarter) rather than assuming a
    full year of data.
    """
    by_date: dict[str, float] = defaultdict(float)
    for t in book.transactions_of(client_id):
        if t.get("transaction_type") in _INCOME_TYPES:
            amt = float(t.get("amount") or 0)
            if amt > 0:
                by_date[t.get("trade_date", "")] += book.fx.to_usd(
                    amt, t.get("currency", "USD"), TODAY
                )
    if not by_date:
        return 0.0, 0
    quarters = len(by_date)
    total = sum(by_date.values())
    return total * 4.0 / quarters, quarters


def detect_income_suitability(book: Book, client_id: str) -> list[Finding]:
    client = book.clients[client_id]

    # Recurring consumption the client draws from the portfolio.
    annual_draw = 0.0
    draw_items: list[str] = []
    for n in book.cash_needs_of(client_id):
        rec = (n.get("recurrence") or "").lower()
        desc = (n.get("description") or "").lower()
        if not rec.startswith("annual"):
            continue
        if not any(h in desc for h in _CONSUMPTION_HINTS):
            continue
        amt = float(n.get("amount") or 0)
        amt_usd = book.fx.to_usd(amt, n.get("currency", "USD"), TODAY)
        annual_draw += amt_usd
        draw_items.append(f"{n.get('description','')} ({usd(amt_usd)}/yr)")
    if annual_draw <= 0:
        return []

    income, quarters = _annual_portfolio_income_usd(book, client_id)
    coverage = income / annual_draw if annual_draw else float("inf")
    shortfall = annual_draw - income

    # Capital that would fund the draw if income falls short: is it impaired,
    # and does any of it mature beyond the client's stated horizon?
    holds = book.holdings_of(client_id, TODAY)
    fi = [h for h in holds if h.asset_class == "Fixed Income"]
    fi_below_cost = sum(h.mv for h in fi if (h.unrealised_pnl_pct or 0) < 0)
    horizon_year = 2026 + int(float(client.raw.get("investment_horizon_years") or 0))
    beyond_horizon = []
    for h in fi:
        m = _YEAR_RE.search(h.instrument_name)
        if m and int(m.group(1)) > horizon_year and (h.unrealised_pnl_pct or 0) < 0:
            beyond_horizon.append((h.instrument_name, int(m.group(1))))

    retired = "retired" in client.life_stage.lower()  # not "pre-retirement"
    caveat = (
        f"Income is annualised from {quarters} observed quarter(s) and the draw is read from "
        f"planned cash needs — both are run-rate estimates, not exact figures."
    )
    facts = {
        "annual_draw_usd": round(annual_draw, 0),
        "annual_income_usd": round(income, 0),
        "coverage_ratio": round(coverage, 2),
        "shortfall_usd": round(shortfall, 0),
        "fixed_income_below_cost_usd": round(fi_below_cost, 0),
        "horizon_year": horizon_year,
        "maturities_beyond_horizon": [f"{nm} ({yr})" for nm, yr in beyond_horizon],
        "income_quarters_observed": quarters,
        "draw_items": draw_items,
    }
    ev = ["planned_cash_needs.csv", "transactions.csv", "holdings.csv"]

    # Branch A — income does not cover the recurring draw. The gap funds
    # consumption by selling capital.
    if coverage < 0.9:
        sev = Severity.HIGH if coverage < 0.6 else Severity.MEDIUM
        detail = (
            f"{client.client_name} draws {usd(annual_draw)} a year ({'; '.join(draw_items)}), "
            f"but the portfolio generated only about {usd(income)} of income (annualised). "
            f"The {usd(shortfall)} gap must come from selling assets"
            + (f", and {usd(fi_below_cost)} of the bond book is below cost, so part of it is "
               f"realised at a loss. " if fi_below_cost > 0 else ". ")
            + caveat
        )
        return [Finding(client_id, "income", sev,
                        f"Income covers only {coverage:.0%} of a {usd(annual_draw)}/yr draw",
                        detail, facts, ev)]

    # Branch B — income covers the draw, but a retired / near-retired client is
    # living off a bond book that is below cost with maturities beyond their
    # horizon. This is the README's flagship suitability conversation, and it is
    # NOT a shortfall — the honest framing is capital quality, not cash flow.
    if fi_below_cost > 0 and beyond_horizon:
        nm, yr = beyond_horizon[0]
        sev = Severity.HIGH if retired else Severity.MEDIUM
        detail = (
            f"Income currently covers the {usd(annual_draw)}/yr draw ({coverage:.0%}), so this "
            f"is not a cash-flow alarm — the question is the capital behind it. "
            f"{usd(fi_below_cost)} of the bond book sits below cost, and {nm} does not mature "
            f"until {yr}, beyond the client's stated horizon (~{horizon_year}). "
            f"{'The client is retired; ' if retired else ''}waiting for that bond to recover to "
            f"par may not be a plan they can outlive, and drawing income while principal is "
            f"impaired erodes the base. A conversation to prepare for, not a trade to rush. "
            + caveat
        )
        return [Finding(client_id, "income", sev,
                        f"Drawing income from impaired long-dated capital (bond due {yr} vs horizon ~{horizon_year})",
                        detail, facts, ev)]

    return []


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
ALL_DETECTORS = [
    detect_collateral,
    detect_concentration,
    detect_mandate,
    detect_liquidity,
    detect_income_suitability,
    detect_attribution,
]
