"""Wealth Intelligence — the intelligence layer between portfolio data and the RM.

SingHacks 2026, Julius Baer track. Pure standard-library Python: no third-party
runtime dependency, so the signal engine runs anywhere a bank would run Python.

Layers:
    data_model   Phase 0. Currency-aware, joined view of the 12 source files.
    lookthrough  Phase 0. Resolves structured products / perpetuals to the
                 single name they are really exposed to.
    detectors    Phase 1. Deterministic risk/opportunity detectors.
    engine       Phase 1. Runs every detector across the book and ranks clients.
"""

from .data_model import Book, load_book

__all__ = ["Book", "load_book"]
