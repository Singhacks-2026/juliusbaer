"""Shared types for Phase 1 — what a detector emits.

Every finding is a self-contained, defensible statement: a severity, a one-line
reason an RM could read aloud, and the exact supporting facts behind it. Nothing
here calls a language model; the explanation layer (Phase 2) consumes these
facts, it does not invent them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Severity(IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    SEVERE = 4

    @property
    def label(self) -> str:
        return self.name.title()


# Map the event_log severity vocabulary onto ours.
EVENT_SEVERITY = {
    "Low": Severity.LOW,
    "Medium": Severity.MEDIUM,
    "High": Severity.HIGH,
    "Severe": Severity.SEVERE,
}


@dataclass
class Finding:
    client_id: str
    category: str          # "collateral" | "concentration" | "mandate" | ...
    severity: Severity
    headline: str          # one line the RM can say in a meeting
    detail: str            # the reasoning, still plain language
    facts: dict[str, Any] = field(default_factory=dict)   # auditable numbers
    evidence: list[str] = field(default_factory=list)     # source rows / notes cited

    def as_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "category": self.category,
            "severity": self.severity.label,
            "severity_rank": int(self.severity),
            "headline": self.headline,
            "detail": self.detail,
            "facts": self.facts,
            "evidence": self.evidence,
        }


def usd(amount: float) -> str:
    """Human money: USD 1.87m, USD 940k, USD 512."""
    a = abs(amount)
    sign = "-" if amount < 0 else ""
    if a >= 1e6:
        return f"{sign}USD {a / 1e6:.2f}m"
    if a >= 1e3:
        return f"{sign}USD {a / 1e3:.0f}k"
    return f"{sign}USD {a:.0f}"
