"""Phase 1 — command-line surface for the signal engine.

    python -m wealth_intelligence                 # the book, triaged
    python -m wealth_intelligence CL-0014         # one client, in depth
    python -m wealth_intelligence --json          # machine-readable, for the UI

This is the substrate the Phase 3 UI renders. It is also the fastest way to
show a judge, in one screen, that the engine understands the book.
"""

from __future__ import annotations

import argparse
import json
import sys

from .data_model import load_book
from .engine import analyse_book, analyse_client
from .findings import Severity, usd

_MARK = {
    Severity.SEVERE: "[SEVERE]",
    Severity.HIGH: "[HIGH]  ",
    Severity.MEDIUM: "[MEDIUM]",
    Severity.LOW: "[LOW]   ",
    Severity.INFO: "[INFO]  ",
}


def _print_book(dossiers) -> None:
    print("=" * 92)
    print("PRISCILLA'S MONDAY MORNING — who to call first")
    print("Asia desk · 20 clients · one relationship manager · today is 2026-08-26")
    print("=" * 92)
    print(f"{'#':>2}  {'Client':<26}{'AUM':>10}  {'Top':<9}{'Why she should call'}")
    print("-" * 92)
    for i, d in enumerate(dossiers, 1):
        lead = d.lead_finding
        if lead is None:
            reason = "No material signals this cycle"
            mark = Severity.INFO.label
        else:
            reason = lead.headline
            mark = lead.severity.label
        print(f"{i:>2}. {d.client_name[:25]:<26}{usd(d.total_usd):>10}  {mark:<9}{reason[:44]}")
    print("-" * 92)
    print("Ranking = sum of severity^2 across each client's findings (deterministic, explainable).")
    print("Run `python -m wealth_intelligence <CLIENT_ID>` for the full reasoning on one client.")


def _print_client(dossier) -> None:
    print("=" * 92)
    print(f"{dossier.client_name}  ({dossier.client_id})   ·   managed book {usd(dossier.total_usd)}")
    print(f"Priority score {dossier.score}   ·   {len(dossier.findings)} findings")
    print("=" * 92)
    if not dossier.findings:
        print("No material signals for this client this cycle.")
        return
    for f in dossier.sorted_findings():
        print(f"\n{_MARK.get(f.severity, '')}  {f.category.upper()}")
        print(f"  {f.headline}")
        print(f"  {f.detail}")
        if f.evidence:
            print(f"  source: {', '.join(f.evidence)}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="wealth_intelligence")
    parser.add_argument("client_id", nargs="?", help="e.g. CL-0014")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--data-dir", help="override the data directory")
    args = parser.parse_args(argv)

    book = load_book(args.data_dir)

    if args.client_id:
        dossier = analyse_client(book, args.client_id)
        if args.json:
            print(json.dumps(dossier.as_dict(), indent=2))
        else:
            _print_client(dossier)
        return 0

    dossiers = analyse_book(book)
    if args.json:
        print(json.dumps([d.as_dict() for d in dossiers], indent=2))
    else:
        _print_book(dossiers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
