# Wealth Intelligence — SingHacks 2026

### From Portfolio Monitoring to Intelligence: Reimagining Wealth Advisory

Everything in `data/` is **synthetic**. The clients, portfolios, holdings and notes were generated
for this hackathon. No real client data is present, and no instrument identifier corresponds to a
real security. Market levels and the event log are calibrated to what actually happened in 2026, so
that portfolio behaviour is explainable against real events.

---

## The scenario

**Priscilla Ong** is a relationship manager on the Asia desk, covering the Singapore and Hong Kong
booking centres. She looks after all 20 clients in this dataset — from a HNW individual with around
USD 8m to a multi-generational family office with USD 88m. That is a realistic book for one RM.

Today is **26 August 2026**. She has client meetings over the next fortnight. For each one she needs
to answer three questions:

1. **What happened to this portfolio this year, and why?**
2. **What is this client exposed to that they don't realise?**
3. **What should we do about it, and how do I explain that to them?**

Build something that helps her answer those questions.

---

## What we're actually judging

**This is not a maths test.** We are not checking whether your percentages agree with ours to two
decimal places. We are checking whether you understood what you were looking at.

A team that says *"this client's bond portfolio is down USD 5.6m"* has done arithmetic.

A team that says *"this client is 71, retired, and drawing USD 1.1m a year from a bond portfolio
that's down USD 5.6m because yields rose after the energy shock. He's told his RM he won't sell at a
loss — but his longest bond doesn't mature until 2045, so 'waiting for it to come back' isn't a plan
he can outlive. Here's how we'd open that conversation"* has understood the client.

The second one wins, even if the first number is more precise.

Concretely, we care about:

- **Reasoning you can defend.** If your tool says a client is at risk, can you show why? An
  insight an RM can't explain to a client in a meeting is not usable.
- **Knowing what matters.** There is far more in this dataset than you can address in a weekend.
  Choosing well is part of the test.
- **Honesty about uncertainty.** Saying "we're not sure, and here's what we'd check" beats a
  confident answer that isn't supported by the data. Confident fabrication scores badly.
- **The human in the loop.** Priscilla stays responsible for the advice. Build for her judgement,
  don't try to replace it.

**Go deep on two or three clients rather than shallow on all twenty.** A demo that genuinely
understands three clients is more convincing than a dashboard that summarises twenty.

---

## What to do with these files

**1. Get the data and load it.** Everything is CSV except the RM notes, which are JSON.
`starter/quickstart.py` loads all of it and prints a client summary — run it first to get oriented.

```bash
git clone https://github.com/kiatgoh-jb/singhacks-test.git
cd singhacks-test
pip install -r requirements.txt
python starter/quickstart.py
```

**2. Read three files by hand before you write any code.** Seriously. Open `clients.csv`,
`rm_notes.json` and `event_log.csv` and just read them. Twenty clients is small enough to hold in
your head, and the notes will tell you things no query will surface.

**3. Pick a client and follow them through time.** `holdings.csv` has five dated snapshots per
portfolio. Pick one client, look at what they held in December 2025 and what they hold now, then
open `event_log.csv` and work out which events touched them. That loop — position, change, cause —
is the core of the whole challenge.

**4. Then decide what to build.** Once you understand a few clients properly, you'll have a much
better sense of what would actually help Priscilla than if you'd started from the tech.

---

## The files

| File | What's in it |
|---|---|
| `clients.csv` | The 20 clients: age, life stage, where their money came from, risk profile, stated objectives |
| `portfolios.csv` | 24 portfolios. Some clients have more than one — this matters |
| `holdings.csv` | Every position, at five dated snapshots. The biggest file, and the centre of gravity |
| `instruments.csv` | What each instrument actually is, including price history and what structured products reference |
| `mandates.csv` | The allocation limits each portfolio is supposed to respect |
| `transactions.csv` | Trades, income, fees, capital calls, credit drawdowns |
| `credit_facilities.csv` | Loans secured against portfolios, with loan-to-value history |
| `commitments.csv` | Money clients have promised to private funds but not yet paid |
| `planned_cash_needs.csv` | What clients will need money for, and when |
| `market_context.csv` | Gold, oil, yields, FX, equity indices at the same five dates |
| `event_log.csv` | What happened in the world in 2026, and how it reached portfolios |
| `rm_notes.json` | Priscilla's own notes. Informal, subjective, and often the most useful file here |

Field-by-field definitions are in [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).

---

## The five snapshot dates

| Date | Why it's there |
|---|---|
| 2025-12-31 | Baseline, before this year's events |
| 2026-02-27 | The day before the Middle East conflict began |
| 2026-03-31 | After the Strait of Hormuz closure |
| 2026-06-30 | Half-year, after the June technology drawdown |
| 2026-08-26 | Today |

One snapshot tells you what a portfolio **is**. Comparing snapshots tells you what **happened**.
Most of the interesting work lives in the comparison.

---

## A few things worth knowing

- **Some clients have more than one portfolio.** A risk can be invisible in each one and obvious
  when you put them together.
- **`event_log.csv` is the authoritative source** for what happened in 2026. If your model's
  recollection of the year disagrees with it, the file wins. Ground your explanations in it rather
  than in what the model thinks it remembers — that's the difference between an auditable
  explanation and a plausible-sounding one.
- **`instruments.underlying_reference` tells you what a structured product is actually exposed
  to.** The asset class tells you what it's called.
- **The RM notes sometimes disagree with the numbers.** That's not a bug. When a client says one
  thing and their portfolio says another, that gap is usually where the real advice is.
- **Private markets valuations lag.** Quarterly-reported funds are normally a quarter behind. That's
  how the industry works, not an error.
- **The data has a small number of real-world imperfections**, the kind that exist in any bank's
  systems. Handling them thoughtfully counts in your favour. Assuming they aren't there doesn't.

---

## Ground rules

- No restrictions on your technology stack.
- Use of AI coding assistants is expected and fine.
- The dataset is for this hackathon only. It's synthetic, but treat it as you would client data —
  that habit is the point.
- If something in the data looks wrong or contradictory, say so in your presentation. Noticing is
  worth more than quietly working around it.

Good luck. Read the notes.
