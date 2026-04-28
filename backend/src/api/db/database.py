"""
SQLite persistence layer for run history, audit, and system state.

The DB path is resolved at call time (not import time) so tests can
redirect writes away from the production DB by setting the
``KARABUK_DB_PATH`` environment variable. This prevents test fixtures
from polluting ``outputs/karabuk_fwi.db`` with evaluation runs that
would otherwise leak into the operational Live Overview card.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from configs.paths import OUTPUTS_DIR
from src.api.run_types import OPERATIONAL_RUN_TYPES, normalize_run_type
from src.api.time_utils import istanbul_now_iso

DEFAULT_DB_PATH = OUTPUTS_DIR / "karabuk_fwi.db"


def _db_path() -> Path:
    """Resolve the DB path lazily so tests can override via env var."""
    override = os.environ.get("KARABUK_DB_PATH")
    if override:
        return Path(override)
    return DEFAULT_DB_PATH


_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS run_history (
    run_id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,
    run_timestamp TEXT NOT NULL,
    target_date TEXT NOT NULL,
    predicted_fwi REAL,
    high_risk_probability REAL,
    high_risk_flag INTEGER,
    decision_reason TEXT,
    drone_triggered INTEGER DEFAULT 0,
    raw_inputs_json TEXT,
    feature_values_json TEXT,
    validation_json TEXT,
    thresholds_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_run_history_type_ts
    ON run_history (run_type, run_timestamp DESC);

CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Detection Alerts moved from JSONL + sidecar to SQLite. The JSONL
-- evidence log at backend/data/notifications/alerts.jsonl is preserved
-- on disk for forensic / external use, but the dashboard reads and
-- writes through this table — including the read/unread state that
-- previously lived in alerts_read_state.json. Snapshot images stay as
-- JPEG files under backend/data/notifications/, referenced by the
-- snapshot_path column.
--
-- Strict invariant: detection_alerts has NO write-path link to
-- run_history. The Option 3 prediction layer never touches this table
-- and the monitoring layer never touches run_history.
CREATE TABLE IF NOT EXISTS detection_alerts (
    alert_id TEXT PRIMARY KEY,
    timestamp_iso TEXT NOT NULL,           -- Istanbul ISO 8601, tz-aware
    timestamp_epoch REAL,                  -- ordering / dedup tiebreak
    label TEXT NOT NULL,                   -- "fire" / "smoke" / etc.
    confidence REAL NOT NULL,              -- max confidence across detections
    source TEXT NOT NULL,                  -- pc_camera / webcam / drone / demo
    camera_id TEXT,                        -- duplicate of source for now;
                                           -- future-proofs multi-camera setups
    severity TEXT,                         -- "info" / "warning" / "critical"
    message TEXT,                          -- human-readable summary
    snapshot_path TEXT,                    -- /static/notifications/<file>.jpg
    is_read INTEGER NOT NULL DEFAULT 0,
    read_at TEXT,                          -- Istanbul ISO 8601 (or NULL)
    detection_count INTEGER NOT NULL DEFAULT 0,
    detections_json TEXT,                  -- per-bbox list, same shape as JSONL
    raw_payload_json TEXT                  -- full original payload, audit-grade
);

CREATE INDEX IF NOT EXISTS idx_detection_alerts_ts
    ON detection_alerts (timestamp_epoch DESC);
CREATE INDEX IF NOT EXISTS idx_detection_alerts_unread
    ON detection_alerts (is_read, timestamp_epoch DESC);
"""


def get_connection() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(_CREATE_TABLES)
    conn.close()


def save_run(run_result: dict):
    conn = get_connection()
    drone_state = run_result.get("drone_state", {})
    # Canonicalize run_type so nothing outside the known taxonomy lands
    # in the DB. Legacy values like 'scheduled_morning' collapse here.
    run_type = normalize_run_type(run_result.get("run_type"))
    conn.execute(
        """INSERT OR REPLACE INTO run_history
           (run_id, run_type, run_timestamp, target_date,
            predicted_fwi, high_risk_probability, high_risk_flag,
            decision_reason, drone_triggered,
            raw_inputs_json, feature_values_json, validation_json, thresholds_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_result["run_id"],
            run_type,
            run_result["run_timestamp"],
            run_result["target_date"],
            run_result.get("predicted_fwi"),
            run_result.get("high_risk_probability"),
            run_result.get("high_risk_flag"),
            run_result.get("decision_reason"),
            int(drone_state.get("active_alert_window", False)),
            json.dumps(run_result.get("raw_inputs", {}), default=str),
            json.dumps(run_result.get("feature_values", {}), default=str),
            json.dumps(run_result.get("validation", {}), default=str),
            json.dumps(run_result.get("thresholds", {}), default=str),
        ),
    )
    conn.commit()
    conn.close()


def _run_type_filter_sql(operational_only: bool) -> tuple[str, tuple]:
    """Build the optional WHERE clause for an operational-only filter."""
    if not operational_only:
        return "", ()
    placeholders = ",".join("?" for _ in OPERATIONAL_RUN_TYPES)
    return f"WHERE run_type IN ({placeholders})", tuple(OPERATIONAL_RUN_TYPES)


# JSON payload columns persisted by save_run(). These hold the full audit
# package (raw inputs, engineered features, validation summary, thresholds)
# that the Features tab renders for the latest operational run.
_JSON_PAYLOAD_COLUMNS = (
    "raw_inputs_json",
    "feature_values_json",
    "validation_json",
    "thresholds_json",
)


def _hydrate_run_row(row: sqlite3.Row | None, include_payload: bool) -> dict | None:
    """
    Return a dict copy of ``row`` with JSON payload columns either:

    * parsed into their object counterparts (``raw_inputs``, ``feature_values``,
      ``validation``, ``thresholds``) when ``include_payload`` is True — this
      is what the Features tab and the Run Detail view consume; or
    * dropped entirely when ``include_payload`` is False — so the list-style
      ``get_run_history`` response stays lean.

    Centralising this here means ``/risk/latest``, ``/history/runs/{id}``,
    and the service layer all see the same shape: the
    ``PredictionResult`` contract documented in ``frontend/src/lib/api.ts``.
    """
    if row is None:
        return None
    out = dict(row)
    for col in _JSON_PAYLOAD_COLUMNS:
        raw = out.pop(col, None)
        if not include_payload:
            continue
        key = col[: -len("_json")]  # raw_inputs_json → raw_inputs
        if raw is None or raw == "":
            out[key] = {}
            continue
        try:
            out[key] = json.loads(raw)
        except (TypeError, ValueError):
            out[key] = {}
    return out


def get_run_history(
    limit: int = 50,
    offset: int = 0,
    operational_only: bool = False,
) -> list[dict]:
    """
    Return a list of runs for the Run History table.

    The heavy JSON payload columns (raw_inputs_json etc.) are **dropped**
    here — the Run History list view never renders them, and including
    them would inflate every page of the history endpoint by several KB
    per row for no benefit. Use ``get_run_by_id`` / ``get_latest_run``
    when the full audit package is required.
    """
    where, params = _run_type_filter_sql(operational_only)
    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM run_history {where} "
        f"ORDER BY run_timestamp DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    conn.close()
    return [_hydrate_run_row(r, include_payload=False) for r in rows]


def get_run_by_id(run_id: str) -> dict | None:
    """Return a single run with the full parsed audit package."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM run_history WHERE run_id = ?", (run_id,)
    ).fetchone()
    conn.close()
    return _hydrate_run_row(row, include_payload=True)


def get_latest_run(operational_only: bool = False) -> dict | None:
    """
    Return the most recent run with the full parsed audit package.

    Set ``operational_only=True`` to restrict to run_types in
    OPERATIONAL_RUN_TYPES (manual / scheduled). This is what the Live
    Overview card and the Features tab both use so that test / evaluation
    rows never appear as the live operational latest result, and so that
    the Features tab always reflects the most recent *operational* run.
    """
    where, params = _run_type_filter_sql(operational_only)
    conn = get_connection()
    row = conn.execute(
        f"SELECT * FROM run_history {where} "
        f"ORDER BY run_timestamp DESC LIMIT 1",
        params,
    ).fetchone()
    conn.close()
    return _hydrate_run_row(row, include_payload=True)


def set_system_state(key: str, value: dict):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO system_state (key, value_json, updated_at) VALUES (?, ?, ?)",
        (key, json.dumps(value, default=str), istanbul_now_iso()),
    )
    conn.commit()
    conn.close()


def get_system_state(key: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT value_json FROM system_state WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    return json.loads(row["value_json"]) if row else None
