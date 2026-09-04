"""Phase 1 — the book-wide engine.

Runs every detector for every client, then answers the question the challenge
puts at the centre of the RM's morning: *who do I call first, and can I defend
the ranking?*

The ranking is deterministic and explainable: a client's priority score is the
sum of their findings' severities, with the single most severe finding breaking
ties, so an RM can always see exactly why one client outranks another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .data_model import Book
from .detectors import ALL_DETECTORS
from .findings import Finding, Severity


@dataclass
class ClientDossier:
    client_id: str
    client_name: str
    total_usd: float
    findings: list[Finding] = field(default_factory=list)

    @property
    def top_severity(self) -> Severity:
        return max((f.severity for f in self.findings), default=Severity.INFO)

    @property
    def score(self) -> float:
        # Weight severe findings super-linearly so one genuine emergency
        # outranks a pile of minor drift.
        return sum(int(f.severity) ** 2 for f in self.findings)

    @property
    def lead_finding(self) -> Finding | None:
        if not self.findings:
            return None
        return sorted(self.findings, key=lambda f: (-int(f.severity), f.category))[0]

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (-int(f.severity), f.category))

    def as_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "total_usd": round(self.total_usd, 0),
            "score": self.score,
            "top_severity": self.top_severity.label,
            "findings": [f.as_dict() for f in self.sorted_findings()],
        }


def analyse_client(book: Book, client_id: str) -> ClientDossier:
    findings: list[Finding] = []
    for detector in ALL_DETECTORS:
        try:
            findings.extend(detector(book, client_id))
        except Exception as exc:  # a detector fault must not sink the whole book
            findings.append(
                Finding(
                    client_id=client_id,
                    category="engine-error",
                    severity=Severity.INFO,
                    headline=f"Detector {detector.__name__} could not run",
                    detail=str(exc),
                )
            )
    client = book.clients[client_id]
    return ClientDossier(
        client_id=client_id,
        client_name=client.client_name,
        total_usd=book.total_usd(client_id),
        findings=findings,
    )


def analyse_book(book: Book) -> list[ClientDossier]:
    """Every client, ranked most-urgent first."""
    dossiers = [analyse_client(book, cid) for cid in book.client_ids()]
    dossiers.sort(key=lambda d: (-d.score, -int(d.top_severity), -d.total_usd))
    return dossiers
