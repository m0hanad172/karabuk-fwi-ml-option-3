"""Service layer for run history and audit.

The DB layer (``src.api.db.database``) now hydrates JSON payload columns
into their object counterparts itself, so this module is a thin pass-through.
It still exists so the route layer has a stable service boundary and so
future history filtering / projection logic has an obvious home.
"""
from __future__ import annotations

from src.api.db.database import get_run_by_id, get_run_history


def list_runs(limit: int = 50, offset: int = 0) -> list[dict]:
    """Return the run history list.

    The returned rows do NOT include the heavy JSON audit payloads — that
    is a deliberate DB-layer choice to keep the list endpoint small. Use
    ``get_run_detail`` when the full audit package is needed.
    """
    return get_run_history(limit=limit, offset=offset)


def get_run_detail(run_id: str) -> dict | None:
    """Return a single run with the full parsed audit package."""
    return get_run_by_id(run_id)
