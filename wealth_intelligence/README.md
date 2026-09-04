# Wealth Intelligence — signal engine (Phase 0 + Phase 1)

The intelligence layer between portfolio data and the Relationship Manager.
This package answers the challenge's first question — *who does Priscilla call
first, and can she defend the ranking?* — from the raw dataset, with every
number traceable back to a source row.

## Run it

No install required. Pure standard-library Python 3.9+ (no pandas, no network).

```bash
# The whole book, triaged — who to call first
python -m wealth_intelligence

# One client, full reasoning
python -m wealth_intelligence CL-0014

# Machine-readable (this is what the Phase 3 UI will render)
python -m wealth_intelligence --json
python -m wealth_intelligence CL-0014 --json

# Tests
python -m unittest discover -s tests
```

## Architecture

```
data/ (12 source files)
        │
        ▼
  data_model.py     Phase 0 · one joined, currency-aware, indexed Book.
  lookthrough.py    Phase 0 · resolves structured products / perpetuals to the
                              single NAME they are really exposed to.
        │
        ▼
  detectors.py      Phase 1 · five deterministic detectors. Each emits Findings
                              with a severity, a one-line reason, and the exact
                              facts behind it. No language model is involved.
        │
        ▼
  engine.py         Phase 1 · runs every detector across all 20 clients and
                              ranks them (score = Σ severity², deterministic).
  cli.py            Phase 1 · the triage view and per-client drill-down.
```

**Why deterministic, and why that matters for the judging.** The engine computes
every signal from the files. A language model's only job (Phase 2) is to *explain*
these facts in plain language and draft actions — it never invents a number or
free-associates about the world. That separation is the compliance,
explainability and auditability story: an insight an RM cannot defend in front of
a client is not usable, so every Finding carries its `evidence` (the source rows)
and `facts` (the numbers).

## The six detectors

| Detector | What it catches |
|---|---|
| `detect_collateral` | Lombard/term LTV vs the margin-call trigger, traced across all five snapshots. Fires SEVERE on **CL-0014** (69.4% vs a 70% call) and **CL-0002**. |
| `detect_concentration` | Single-name exposure across the whole household, **looking through** structured products and perpetuals to the name (Golden Harbour = stock + perpetual + accumulator). Separates managed (mandate-governed) from custody (client-directed legacy). |
| `detect_mandate` | Allocation-band and single-position breaches, plus **sustainable-mandate exclusion** breaches (CL-0005 holds excluded energy/palm names in a SUSBAL mandate). Custody accounts are excluded — they are not measured against a mandate. |
| `detect_liquidity` | Confirmed near-term cash needs and uncalled commitments vs what is genuinely sellable — **netting out collateral pledged** to a facility, and flagging currency mismatch and gated funds. |
| `detect_income_suitability` | Recurring drawdown vs the income the portfolio actually pays. Flags a genuine **shortfall** (CL-0006), and — distinctly — a retiree **drawing on impaired long-dated capital** whose bonds mature beyond their horizon (**CL-0012**, the README's flagship case). Honest about annualised run-rate estimates. |
| `detect_attribution` | The largest USD moves since the year-end baseline, tied to the **authoritative `event_log.csv`** by transmission channel — grounded explanation, not memory. |

## Data handling decisions (the traps this dataset sets)

- **Currency.** Position value comes from `holdings.market_value_usd` at each
  snapshot, never from the `aum_<date>` columns in `portfolios.csv` (those are in
  base currency; only `aum_usd_current` is USD). This avoids reading a HKD→USD
  conversion as a loss.
- **LTV** is read as `drawn / lending_value` (already advance-rate haircut), per
  the data dictionary — not recomputed from raw market value.
- **Custody accounts** count toward the household risk picture but are never
  reported as mandate breaches.
- **Encumbered assets** pledged to a facility are subtracted from "sellable"
  liquidity — a book that looks liquid can be anything but.
- **Look-through** uses an explicit, auditable alias table (`lookthrough.py`),
  justified by `instruments.underlying_reference` and
  `concentration_limit_applies`.

## Phase 2 — grounded explanation (`explainer.py`)

Turns a client's Findings into language the RM can use: a situation summary, a
few talking points / actions to consider, and honest watch-outs. The model is
handed only the computed facts, the client profile, the RM notes and the
relevant event rows, and is told to reason strictly from them — it explains, it
never computes. Every explanation is cached to disk (`.wi_cache/`), and the
layer falls back to a deterministic summary when there is no API key or network,
so the app always works.

```bash
export ANTHROPIC_API_KEY=sk-ant-...          # optional; enables live grounding
python scripts/pregenerate.py CL-0014 CL-0012 CL-0017   # cache the hero clients
```

## Phase 3 — the RM workbench (`streamlit_app.py`)

```bash
pip install -r requirements-app.txt
streamlit run streamlit_app.py
```

Three zones: **Book** (triage — who to call first) → **Client** (a grounded
explanation + a look-through exposure snapshot) → **Signals** (every finding
with a "Why?" expander showing the exact facts, and Accept / Edit / Dismiss so
the RM stays in control).
