"""Pre-generate grounded explanations and cache them to disk.

Run this ONCE before the demo, with your key set in the environment, so the live
demo serves every explanation from cache and never depends on the venue network:

    export ANTHROPIC_API_KEY=sk-ant-...      # your NEW key; never commit it
    python scripts/pregenerate.py            # all 20 clients
    python scripts/pregenerate.py CL-0014 CL-0012 CL-0017   # just the heroes

The key is read from the environment by the Anthropic SDK. It is never written
to disk or into the cache — only the generated explanations are cached, under
.wi_cache/ (git-ignored).
"""

from __future__ import annotations

import os
import sys

from wealth_intelligence.data_model import load_book
from wealth_intelligence.engine import analyse_client, analyse_book
from wealth_intelligence.explainer import explain


def main(argv: list[str]) -> int:
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("No ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN set — nothing to pre-generate.")
        print("The app still runs; it will use the deterministic offline explanations.")
        return 1

    book = load_book()
    targets = argv[1:] or [d.client_id for d in analyse_book(book)]
    print(f"Pre-generating {len(targets)} explanation(s) with model "
          f"{os.environ.get('WI_MODEL', 'claude-opus-5')}…\n")

    ok = 0
    for cid in targets:
        dossier = analyse_client(book, cid)
        exp = explain(book, dossier, use_cache=True)
        tag = "grounded" if exp.grounded_by_model else "FALLBACK (check key/network)"
        print(f"  {cid}  {dossier.client_name:<28} [{tag}]")
        ok += int(exp.grounded_by_model)
    print(f"\nDone: {ok}/{len(targets)} grounded and cached under .wi_cache/")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
