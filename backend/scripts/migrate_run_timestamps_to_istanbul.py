"""
One-shot migration: rewrite legacy naive-UTC ``run_timestamp`` values in
``run_history`` as tz-aware Istanbul ISO 8601 strings.

Why this exists
---------------
Before the timezone fix, ``src/pipeline/live_inference.py`` stamped every
run with ``datetime.utcnow().isoformat()``, producing naive strings like
``"2026-04-15T08:00:00.123456"``. The frontend then parsed those as
*local* Istanbul time and displayed them three hours early. All new rows
are now written as tz-aware Istanbul strings, but existing rows still
have the old format — this script rewrites them so the Run History tab
shows the correct moments.

Detection rule: a string with no ``+``/``-`` offset and no trailing ``Z``
is treated as naive UTC and rewritten as the equivalent Istanbul moment.
Anything that already has an offset is left alone.

Usage
-----
    "C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe" \
        scripts/migrate_run_timestamps_to_istanbul.py

Safe to re-run: the detection rule is idempotent, rows that are already
tz-aware are skipped.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Make the backend package roots importable when this script is invoked
# directly (`python backend/scripts/migrate_run_timestamps_to_istanbul.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.db.database import get_connection
from src.api.time_utils import ISTANBUL_TZ

UTC = ZoneInfo("UTC")


def _has_offset(s: str) -> bool:
    """Return True if the string already carries a timezone designator."""
    if not s:
        return False
    if s.endswith("Z"):
        return True
    # Look for +HH:MM or -HH:MM in the last 6 chars (avoid matching the
    # "-" inside the date portion).
    tail = s[-6:]
    return ("+" in tail) or (tail.startswith("-") or tail[0:1] == "-")


def _naive_utc_to_istanbul_iso(s: str) -> str:
    """Interpret a naive ISO string as UTC and return Istanbul ISO 8601."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(ISTANBUL_TZ).isoformat()


def migrate() -> None:
    conn = get_connection()
    rows = conn.execute(
        "SELECT run_id, run_timestamp FROM run_history"
    ).fetchall()

    updated = 0
    skipped = 0
    for row in rows:
        ts = row["run_timestamp"]
        if not ts or _has_offset(ts):
            skipped += 1
            continue
        try:
            new_ts = _naive_utc_to_istanbul_iso(ts)
        except ValueError:
            print(f"  skip unparseable: {row['run_id']} {ts!r}")
            skipped += 1
            continue
        conn.execute(
            "UPDATE run_history SET run_timestamp = ? WHERE run_id = ?",
            (new_ts, row["run_id"]),
        )
        updated += 1

    conn.commit()
    conn.close()

    print(f"run_history migration complete: {updated} updated, {skipped} skipped")


if __name__ == "__main__":
    migrate()
