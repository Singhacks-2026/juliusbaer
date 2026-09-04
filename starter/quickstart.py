"""
SingHacks 2026 - Julius Baer Wealth Intelligence
Quickstart: loads every file and prints enough to get oriented.

    pip install pandas
    python starter/quickstart.py

This deliberately does not compute anything clever. It is here so you can see
the shape of the data in 30 seconds and then go and think.
"""
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")


def load(name):
    return pd.read_csv(os.path.join(DATA, name))


clients = load("clients.csv")
portfolios = load("portfolios.csv")
holdings = load("holdings.csv")
instruments = load("instruments.csv")
mandates = load("mandates.csv")
transactions = load("transactions.csv")
facilities = load("credit_facilities.csv")
commitments = load("commitments.csv")
cash_needs = load("planned_cash_needs.csv")
market = load("market_context.csv")
events = load("event_log.csv")

with open(os.path.join(DATA, "rm_notes.json"), encoding="utf-8") as f:
    notes = json.load(f)

DATES = sorted(holdings["snapshot_date"].unique())
TODAY = DATES[-1]

print("=" * 78)
print("FILES LOADED")
print("=" * 78)
for name, df in [
    ("clients", clients), ("portfolios", portfolios), ("holdings", holdings),
    ("instruments", instruments), ("mandates", mandates), ("transactions", transactions),
    ("credit_facilities", facilities), ("commitments", commitments),
    ("planned_cash_needs", cash_needs), ("market_context", market), ("event_log", events),
]:
    print(f"  {name:<22} {len(df):>5} rows   {len(df.columns):>2} columns")
print(f"  {'rm_notes':<22} {len(notes):>5} notes")
print(f"\n  Snapshot dates: {', '.join(DATES)}")
print(f"  'Today' in this dataset: {TODAY}")

print("\n" + "=" * 78)
print(f"THE BOOK  ({len(clients)} clients, one relationship manager)")
print("=" * 78)
print(f"{'ID':<9}{'Client':<28}{'AUM USDm':>9}  {'Band':<6}{'Ctr':<4}{'Life stage'}")
print("-" * 78)
for _, c in clients.sort_values("total_aum_usd", ascending=False).iterrows():
    print(f"{c.client_id:<9}{c.client_name[:26]:<28}{c.total_aum_usd/1e6:>9.1f}  "
          f"{c.wealth_band:<6}{c.booking_centre[:2]:<4}{c.life_stage[:30]}")
print("-" * 78)
print(f"{'':<9}{'TOTAL':<28}{clients.total_aum_usd.sum()/1e6:>9.1f}")

print("\n" + "=" * 78)
print("WHAT HAPPENED IN 2026  (event_log.csv is the authoritative source)")
print("=" * 78)
for _, e in events.iterrows():
    print(f"  {e.event_date}  [{e.severity:<6}] {e.description[:88]}")

print("\n" + "=" * 78)
print("MARKET CONTEXT AT EACH SNAPSHOT")
print("=" * 78)
watch = ["SPX", "GOLD_USD_OZ", "BRENT_USD_BBL", "UST_10Y_PCT", "USDSGD", "VIX"]
piv = (market[market.series_id.isin(watch)]
       .pivot(index="series_id", columns="snapshot_date", values="value")
       .reindex(watch))
print(piv.to_string())

print("\n" + "=" * 78)
print("EXAMPLE: ONE CLIENT THROUGH TIME")
print("=" * 78)
cid = clients.sort_values("total_aum_usd", ascending=False).iloc[0].client_id
name = clients.loc[clients.client_id == cid, "client_name"].iloc[0]
print(f"Client {cid} - {name}\n")

for pid in portfolios.loc[portfolios.client_id == cid, "portfolio_id"]:
    row = portfolios.loc[portfolios.portfolio_id == pid].iloc[0]
    print(f"  {pid}  {row.portfolio_name}  ({row.service_model}, {row.mandate_name}, {row.base_currency})")

h = holdings[(holdings.client_id == cid) & (holdings.snapshot_date == TODAY)]
print(f"\n  Largest positions today, as a share of everything this client holds:")
tot = h.market_value_usd.sum()
top = (h.groupby("instrument_name").market_value_usd.sum()
       .sort_values(ascending=False).head(5))
for nm, v in top.items():
    print(f"    {100*v/tot:>5.1f}%  {nm[:58]:<58} USD {v/1e6:>6.2f}m")

print(f"\n  What Priscilla wrote about this client:")
for n in [x for x in notes if x["client_id"] == cid]:
    print(f"    {n['note_date']} ({n['channel']}): {n['note'][:150]}...")

print("\n" + "=" * 78)
print("NOW GO AND READ clients.csv, rm_notes.json AND event_log.csv YOURSELF.")
print("Twenty clients is small enough to actually read. Start there, not here.")
print("=" * 78)
