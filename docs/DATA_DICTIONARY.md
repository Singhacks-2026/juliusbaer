# Data Dictionary

Field-level reference for the SingHacks 2026 Julius Baer dataset. Start with the [README](../README.md) — this file is for looking things up.

---

## Files

| File | Rows | Grain |
|---|---|---|
| `clients.csv` | 20 | one row per client |
| `portfolios.csv` | 24 | one row per portfolio (some clients hold several) |
| `holdings.csv` | 1,015 | one row per position **per snapshot date** |
| `instruments.csv` | 62 | one row per instrument, including full price history |
| `mandates.csv` | 48 | strategic asset allocation bands, one row per mandate × asset class |
| `transactions.csv` | 393 | trades, income, fees, capital calls, facility activity |
| `credit_facilities.csv` | 5 | Lombard and term facilities with LTV history |
| `commitments.csv` | 5 | outstanding private markets commitments |
| `planned_cash_needs.csv` | 20 | known and expected future liabilities |
| `market_context.csv` | 115 | 23 market series × 5 snapshot dates |
| `event_log.csv` | 16 | dated 2026 events with transmission channels |
| `rm_notes.json` | 28 | free-text relationship manager notes |

### Joining the data

```
clients.client_id  →  portfolios.client_id  →  holdings.portfolio_id
holdings.instrument_id  →  instruments.instrument_id
portfolios.mandate_code  →  mandates.mandate_code
holdings.snapshot_date  →  market_context.snapshot_date
credit_facilities.collateral_portfolio_id  →  portfolios.portfolio_id
rm_notes[].client_id  →  clients.client_id
```

---

## Field definitions

### clients.csv

| Column | Notes |
|---|---|
| `client_id` | `CL-nnnn` |
| `age`, `gender`, `nationality`, `country_of_residence`, `tax_domicile` | Residence and tax domicile frequently differ. This matters for suitability and tax-aware advice. |
| `booking_centre` | Singapore or Hong Kong |
| `rm_id`, `rm_name`, `rm_desk` | Covering relationship manager. All 20 clients sit with the same RM, so this is constant across the book. |
| `base_currency` | Reporting currency for the client |
| `wealth_band` | HNW (under USD 30m) or UHNW (USD 30m and above) |
| `total_aum_usd` | Sum of all portfolios at the current snapshot |
| `life_stage` | Free text, e.g. pre-liquidity event, succession planning |
| `source_of_wealth` | Where the money came from. Read this alongside the portfolio. |
| `risk_profile`, `risk_tolerance_score` | Score is 1 (lowest) to 10 (highest) |
| `investment_horizon_years`, `liquidity_needs` | Liquidity need is Low / Medium / High |
| `objectives` | Stated client objectives, in the client's own framing |
| `kyc_review_due` | Some are overdue relative to today |

### portfolios.csv

`portfolio_id`, `client_id`, `portfolio_name`, `mandate_code`, `mandate_name`,
`service_model` (Discretionary / Advisory / Custody), `base_currency`, `inception_date`,
`benchmark`, `aum_<date>` for each of the five snapshots, and `aum_usd_current`.

**Custody accounts are not managed by the bank and are not measured against a mandate.** They still
form part of the client's total wealth picture.

### holdings.csv

| Column | Notes |
|---|---|
| `snapshot_date` | One of the five dates above |
| `quantity` | For bonds, quantity is expressed in **units of 100 nominal**, so market value is `quantity × price_local`. The same formula holds for every asset class. |
| `price_local`, `instrument_ccy` | Price in the instrument's own currency |
| `market_value_local` / `market_value_base` / `market_value_usd` | Base is the portfolio's reporting currency |
| `weight_pct` | Share of that portfolio at that snapshot |
| `avg_cost_local`, `cost_basis_base`, `unrealised_pnl_base`, `unrealised_pnl_pct` | Cost basis is struck at the exchange rate prevailing when the position was acquired |
| `lending_value_base`, `advance_rate_pct` | Collateral value for Lombard purposes. Illiquid alternatives carry a 0% advance rate. |
| `liquidity_tier` | Daily / Weekly / Monthly / Quarterly Gate / Illiquid |
| `valuation_date` | Usually equals `snapshot_date`. It does not always. |

### instruments.csv

Includes `asset_class`, `sub_asset_class`, `sector`, `region`, `currency`, `liquidity_tier`,
`price_<date>` for all five snapshots, and three fields worth particular attention:

- **`underlying_reference`** — for structured products, the actual underlying basket. A structured
  product's asset class tells you what it is; this field tells you what you are exposed to.
- **`sustainability_excluded`** — `Y` if the instrument falls within the exclusions binding on
  sustainable mandates.
- **`concentration_limit_applies`** — `Y` for single-name and single-asset exposures. The mandate
  single-position limit is intended to apply to these, not to diversified funds, sovereign bonds or
  deposits.

### mandates.csv

`min_pct`, `target_pct` and `max_pct` per asset class, plus `max_single_position_pct` and
`mandate_notes`. The Sustainable Balanced mandate carries binding exclusions set out in
`mandate_notes`.

### credit_facilities.csv

Loan-to-value is calculated as `drawn ÷ lending_value`, where lending value is market value after
per-asset advance-rate haircuts — not raw market value. `margin_call_ltv_pct` is the trigger.
`headroom_<date>` is how much lending value exceeds the drawn amount.

### market_context.csv

Long format: `snapshot_date`, `series_id`, `series_name`, `category`, `unit`, `value`. Covers equity
indices, gold, Brent, TTF gas, US Treasury yields, the fed funds target, US CPI, VIX and ten
currency pairs.

### event_log.csv

`event_date`, `event_type`, `region`, `description`, `primary_transmission`, `severity`. The
`primary_transmission` field names the channels through which each event reached portfolios — the
intended bridge between an event and a holding.

### rm_notes.json

`note_id`, `client_id`, `note_date`, `rm_id`, `rm_name`, `channel`, `note`. Written the way RMs
actually write: partial, subjective, occasionally in tension with the structured data. Some notes
contain information that appears nowhere else. Some contain client statements that the portfolio
does not support.

---

## Conventions and caveats

- **All monetary values are unrounded floats.** Format for display as you see fit.
- **FX convention:** `market_context.csv` quotes each pair in its market convention
  (`USDSGD` is SGD per USD; `EURUSD` is USD per EUR). Check before you divide.
- **Bond quantities** are in units of 100 nominal, as above.
- **Private markets marks lag.** Private equity and private real estate report quarterly and the
  reported mark is typically one quarter behind. This is normal, not an error.
- **This dataset contains a small number of data-quality artefacts of the kind present in real
  production banking data.** They are neither numerous nor severe, and they are there deliberately.
  A solution that handles them gracefully is worth more than one that assumes perfect inputs.

---

## Directions the data supports

The case asks you to move from *"What does my client's portfolio look like?"* to *"What should I
know, and what should I do next?"* Some directions the data supports:

- **Explanation.** Attribute a portfolio's year-to-date change to specific events. "Down 4.1%" is a
  number; "down 4.1%, of which 3.3 points came from duration as the 10-year moved from 4.05% to
  4.66%, partly offset by gold" is an explanation.
- **Risk that is not on the report.** Concentration that only appears when you aggregate across a
  client's portfolios, or look through a structured product to its underlying basket, or notice that
  a client's largest holding and their source of wealth are the same bet.
- **Suitability and mandate governance.** Which portfolios sit outside their bands, which breaches
  are drift and which are client-directed, and which have a waiver on file in the RM notes.
- **Liquidity.** Match `planned_cash_needs.csv` and `commitments.csv` against what is actually
  sellable at `liquidity_tier` Daily. Several clients cannot fund what they have committed to.
- **Collateral.** Trace LTV through the five snapshots. At least one facility breached its trigger
  during the period. At least one was cured by an event rather than by an action.
- **Tax-aware optimisation.** Look at unrealised gains and losses side by side within a household,
  and at `tax_domicile` rather than `country_of_residence`.
- **Life events.** `objectives`, `life_stage` and `planned_cash_needs.csv` describe futures that
  the current allocations are not always built for.
- **Scenario analysis.** The Strait of Hormuz situation is unresolved as of today. What happens to
  each portfolio if it reopens? If it escalates further?
- **The RM's own workflow.** Twenty clients, five snapshots, 1,015 positions, one relationship
  manager. What needs surfacing first thing on a Monday, and how would you rank it?

Governance, explainability and the ability to show a client *why* a recommendation was made are part
of the judging criteria. An insight a relationship manager cannot defend in front of a client is not
usable.

---

*Synthetic dataset prepared for SingHacks 2026. Not investment advice. Not for any use outside the
hackathon.*
