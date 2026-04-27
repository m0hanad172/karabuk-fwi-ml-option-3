"""
Operational time helpers.

Single source of truth for all timestamps that cross the API boundary or
land in the SQLite run_history table.

Why this module exists
----------------------
The project scope is Karabük, Turkey, and every display on the dashboard
(Live Overview, Run History, Scheduler card, Monitoring notifications)
presents time in ``Europe/Istanbul`` (TRT). Earlier revisions wrote run
timestamps with ``datetime.utcnow().isoformat()``, producing **naive** ISO
strings like ``"2026-04-15T08:00:00.123456"`` — no ``Z``, no offset. Per
the ECMAScript spec, a naive ISO date-time is parsed by the browser as
*local* time, so the UTC instant (08:00 UTC = 11:00 Istanbul) was rendered
as 08:00 Istanbul — the canonical "three hours off" bug.

Rule going forward
------------------
Every operational time that will be serialised, stored, or shown on the
dashboard MUST be a tz-aware ``datetime`` in ``Europe/Istanbul`` and MUST
be emitted via ``.isoformat()`` so the frontend's ``new Date(...)`` can
round-trip it safely.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from configs.settings import DISPLAY_TIMEZONE

#: Single shared ``ZoneInfo`` instance for the operational timezone.
ISTANBUL_TZ: ZoneInfo = ZoneInfo(DISPLAY_TIMEZONE)


def istanbul_now() -> datetime:
    """Return a tz-aware ``datetime`` in ``Europe/Istanbul``."""
    return datetime.now(ISTANBUL_TZ)


def istanbul_now_iso() -> str:
    """
    Return the current Istanbul moment as a strict ISO 8601 string.

    Example: ``"2026-04-15T11:00:00.123456+03:00"``. Always tz-aware so
    the browser parses it unambiguously.
    """
    return istanbul_now().isoformat()


def istanbul_today() -> date:
    """Return today's *Istanbul-local* date, not the UTC date."""
    return istanbul_now().date()


def istanbul_today_str() -> str:
    """Istanbul-local date as ``YYYY-MM-DD``."""
    return istanbul_today().isoformat()


def to_istanbul_iso(dt: datetime) -> str:
    """
    Convert any ``datetime`` to a tz-aware Istanbul ISO 8601 string.

    If the input is naive, it is assumed to be UTC (that is how the legacy
    pipeline stored ``run_timestamp``) and is localized accordingly. This
    is what the one-shot DB migration uses to rewrite legacy rows.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ISTANBUL_TZ).isoformat()
