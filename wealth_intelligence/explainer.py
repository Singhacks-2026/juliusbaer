"""Phase 2 — grounded natural-language explanation.

The deterministic engine (Phase 1) decides *what is true*. This layer turns a
client's Findings into language an RM can use in a meeting: a short situation
summary, two or three suggested talking points / actions, and an honest list of
what to check. The model is handed only the computed facts, the client's own
profile and objectives, the RM's notes, and the authoritative event rows — and
is instructed to reason *only* from them. It never invents a number and never
free-associates about the world. That separation is the compliance story.

Robustness for a live demo:

* Every explanation is cached to disk (keyed on a hash of its exact inputs), so
  the hero clients can be pre-generated once and the demo runs with no network.
* If there is no API key, or any error, the layer falls back to a deterministic
  explanation assembled from the Findings themselves — the app always works.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from .data_model import Book
from .engine import ClientDossier
from .findings import usd

MODEL = os.environ.get("WI_MODEL", "claude-opus-5")
EFFORT = os.environ.get("WI_EFFORT", "medium")
CACHE_DIR = os.environ.get(
    "WI_CACHE_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), ".wi_cache")
)
PROMPT_VERSION = "v1"

SYSTEM = """You are the explanation layer of a private-bank wealth-intelligence \
system used by a Relationship Manager (RM) at Julius Baer. You do not manage \
money or make decisions — you help the RM understand a client's situation and \
prepare for a conversation.

Absolute rules:
- Reason ONLY from the facts, findings, client profile, RM notes and event rows \
provided in the user message. Never introduce a number, holding, or world event \
that is not in the input. If you are unsure, say so.
- Every claim must be defensible to the client in a meeting. Prefer "we should \
check X" over a confident assertion the data does not support.
- The RM remains responsible for all advice. Suggest actions "to consider", \
never instructions. Respect the client's stated objectives, mandate and risk \
profile.
- Be concise and concrete. Money in plain terms (USD 1.9m, not 1900000).

Return ONLY a JSON object, no prose around it, with exactly these keys:
{
  "situation": "3-4 sentences: what is happening and why it matters to THIS client",
  "talking_points": ["2-4 short, specific things the RM could raise or do, each with its reason"],
  "watch_outs": ["1-3 honest uncertainties, data caveats, or things to verify first"]
}"""


@dataclass
class Explanation:
    situation: str
    talking_points: list[str]
    watch_outs: list[str]
    grounded_by_model: bool  # True if produced by Claude, False if deterministic fallback

    def as_dict(self) -> dict[str, Any]:
        return {
            "situation": self.situation,
            "talking_points": self.talking_points,
            "watch_outs": self.watch_outs,
            "grounded_by_model": self.grounded_by_model,
        }


# --------------------------------------------------------------------------- #
# Build the grounded context handed to the model
# --------------------------------------------------------------------------- #
def _relevant_events(book: Book, dossier: ClientDossier) -> list[dict[str, str]]:
    dates = {
        f.facts.get("event_date")
        for f in dossier.findings
        if f.facts.get("event_date")
    }
    picked = [e for e in book.events if e.get("event_date") in dates]
    return [
        {
            "date": e["event_date"],
            "description": e["description"],
            "transmission": e.get("primary_transmission", ""),
            "severity": e.get("severity", ""),
        }
        for e in picked
    ]


def build_context(book: Book, dossier: ClientDossier) -> dict[str, Any]:
    c = book.clients[dossier.client_id]
    return {
        "client": {
            "name": c.client_name,
            "age": c.age,
            "life_stage": c.life_stage,
            "risk_profile": c.risk_profile,
            "liquidity_needs": c.liquidity_needs,
            "objectives": c.objectives,
            "source_of_wealth": c.source_of_wealth,
            "tax_domicile": c.tax_domicile,
            "country_of_residence": c.country_of_residence,
            "total_managed_usd": round(dossier.total_usd, 0),
        },
        "findings": [
            {
                "category": f.category,
                "severity": f.severity.label,
                "headline": f.headline,
                "facts": f.facts,
            }
            for f in dossier.sorted_findings()
        ],
        "rm_notes": [
            {"date": n.get("note_date"), "channel": n.get("channel"), "note": n.get("note")}
            for n in book.notes_of(dossier.client_id)
        ],
        "relevant_events": _relevant_events(book, dossier),
    }


def _cache_key(context: dict[str, Any]) -> str:
    blob = json.dumps(
        {"ctx": context, "model": MODEL, "effort": EFFORT, "prompt": PROMPT_VERSION},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


# --------------------------------------------------------------------------- #
# Deterministic fallback — the app must work with no network / no key
# --------------------------------------------------------------------------- #
def _fallback(book: Book, dossier: ClientDossier) -> Explanation:
    c = book.clients[dossier.client_id]
    lead = dossier.lead_finding
    situation = (
        f"{c.client_name} is {c.life_stage.lower()}, {c.risk_profile.lower()} risk profile, "
        f"with a managed book of {usd(dossier.total_usd)}. "
        + (lead.detail if lead else "No material signals this cycle.")
    )
    points = [f.headline for f in dossier.sorted_findings()[:4]]
    watch = [
        "This summary is assembled directly from the detectors (offline mode); "
        "the model-written narrative was not available.",
    ]
    for f in dossier.findings:
        if f.category == "mandate":
            watch.append(
                "Confirm whether the mandate deviation is client-directed (check the "
                "RM notes / any waiver on file) before treating it as a breach."
            )
            break
    return Explanation(situation, points, watch[:3], grounded_by_model=False)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def explain(book: Book, dossier: ClientDossier, use_cache: bool = True) -> Explanation:
    context = build_context(book, dossier)
    key = _cache_key(context)
    path = os.path.join(CACHE_DIR, f"{dossier.client_id}_{key}.json")

    if use_cache and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            return Explanation(
                d["situation"], d["talking_points"], d["watch_outs"], d.get("grounded_by_model", True)
            )
        except (OSError, KeyError, json.JSONDecodeError):
            pass  # fall through and regenerate

    explanation = _generate(book, dossier, context)

    if explanation.grounded_by_model:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(explanation.as_dict(), fh, indent=2)
        except OSError:
            pass
    return explanation


def _generate(book: Book, dossier: ClientDossier, context: dict[str, Any]) -> Explanation:
    # No key configured anywhere -> deterministic fallback, no import needed.
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return _fallback(book, dossier)
    try:
        import anthropic
    except ImportError:
        return _fallback(book, dossier)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Prepare the RM's read on this client. Use only what is below.\n\n"
                        + json.dumps(context, indent=2, default=str)
                    ),
                }
            ],
        )
        if response.stop_reason == "refusal":
            return _fallback(book, dossier)
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        data = _parse_json(text)
        if data is None:
            return _fallback(book, dossier)
        return Explanation(
            situation=str(data.get("situation", "")).strip(),
            talking_points=[str(x) for x in data.get("talking_points", [])][:4],
            watch_outs=[str(x) for x in data.get("watch_outs", [])][:3],
            grounded_by_model=True,
        )
    except Exception:
        # Any API / network / parsing failure degrades gracefully.
        return _fallback(book, dossier)


def _parse_json(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None
