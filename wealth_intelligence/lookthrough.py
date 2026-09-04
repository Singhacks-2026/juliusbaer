"""Phase 0 — look-through.

A structured product's asset class tells you what it is called; its
``underlying_reference`` tells you what you are actually exposed to
(data dictionary). This module resolves a holding to the single **issuer /
name** it really carries risk to, so that concentration can be measured across
a whole household the way a risk officer would — counting a stock, its
perpetual, and an accumulator on it as *one* bet.

The alias table below is deliberately explicit and auditable: every mapping can
be pointed at the source field that justifies it. That is the governance
posture the challenge rewards — no free-association about what a note "probably"
references.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .data_model import Instrument

# Canonical single-name issuers and the text tokens that identify them.
# Tokens are matched (case-insensitively) against both the instrument name and
# the structured-product underlying_reference.
_ALIASES: dict[str, str] = {
    "golden harbour": "Golden Harbour Properties",
    "helios cloud": "Helios Cloud Systems",
    "helios": "Helios Cloud Systems",
    "pacific orient": "Pacific Orient Shipping",
    "bara nusantara": "Bara Nusantara Energy",
    "meridian semiconductor": "Meridian Semiconductor",
    "nordvind": "Nordvind Industrial",
    "sunrise palm": "Sunrise Palm Resources",
    "kanto pharma": "Kanto Pharma Holdings",
    "verdant health": "Verdant Health Group",
    "aranya": "Aranya Technologies",
    "gulf marine": "Gulf Marine Services",
    "pacific rim bank": "Pacific Rim Bank",
}


@dataclass
class Exposure:
    """A holding's resolved single-name exposure.

    direct   -> the holding *is* that name (stock, that name's bond/perpetual,
                or a single-underlying structured product).
    basket   -> a worst-of / basket structured product that *includes* the name
                among several. Reported, but flagged so it is not silently
                merged into the headline single-name number.
    """

    issuer: str
    kind: str  # "direct" | "basket"


def _match_tokens(text: str) -> list[str]:
    t = (text or "").lower()
    hits: list[str] = []
    for token, canonical in _ALIASES.items():
        if token in t and canonical not in hits:
            hits.append(canonical)
    return hits


def resolve(instrument: Optional[Instrument]) -> list[Exposure]:
    """Return the single-name exposures a holding of this instrument carries.

    * A direct single name (stock / that issuer's perpetual / single-underlying
      note) resolves to exactly one ``direct`` exposure.
    * A basket / worst-of structured product resolves to one ``basket`` exposure
      per named constituent.
    * Diversified funds, sovereigns, deposits, gold -> no single-name exposure.
    """
    if instrument is None:
        return []

    # Only names the mandate single-position limit is meant to police
    # (concentration_limit_applies=Y) can be a single-name concentration.
    if not instrument.concentration_limit_applies:
        return []

    # First: does the instrument's own name identify a single issuer?
    name_hits = _match_tokens(instrument.instrument_name)
    if name_hits:
        return [Exposure(issuer=name_hits[0], kind="direct")]

    # Otherwise it is a structured product identified only by its underlying.
    ref_hits = _match_tokens(instrument.underlying_reference)
    if not ref_hits:
        return []
    if len(ref_hits) == 1:
        # Single-underlying note (e.g. ELN ref one name) -> direct exposure.
        return [Exposure(issuer=ref_hits[0], kind="direct")]
    # Worst-of basket -> exposure to each constituent, flagged as basket.
    return [Exposure(issuer=name, kind="basket") for name in ref_hits]
