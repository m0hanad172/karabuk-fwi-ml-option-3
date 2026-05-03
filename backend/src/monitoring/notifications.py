"""SQLite-backed fire-detection notifications.

This is the *only* place monitoring writes observations. Notifications
are strictly separated from ``run_history`` (the Option 3 prediction
audit log) and never modify ``predicted_fwi`` or ``high_risk_flag``.
They are an operational alerting channel, not a data source for the
model.

Two-tier storage
----------------
1. **In-memory ring buffer** — the most-recent alerts kept hot for the
   live Monitoring feed (``GET /monitoring/notifications``). Rebuilt
   from SQLite at startup so a restart does not appear to "lose" the
   live feed.
2. **SQLite ``detection_alerts`` table** — durable read/write store
   for the Detection Alerts tab. Replaces the previous JSONL +
   sidecar JSON design. Carries id, timestamp, label, confidence,
   source, snapshot path, ``is_read`` flag, ``read_at``, the full
   per-detection list, and a raw payload column for forensic use.

Snapshots themselves remain on disk as JPEG files under
``backend/data/notifications/`` and are referenced by ``snapshot_path``
in the SQLite row. They are served via the ``/static/notifications/``
static mount mounted in ``src/api/main.py``.

Migration from JSONL
--------------------
The legacy ``alerts.jsonl`` file (and the legacy
``alerts_read_state.json`` sidecar) are read once on startup by
``import_legacy_jsonl()``. Any alert whose id is not yet in
``detection_alerts`` is inserted; existing rows are left untouched, so
the import is idempotent and safe to re-run. The on-disk JSONL file
is preserved for forensic / external use — no destructive cleanup.

After the first import, the JSONL file is no longer written to. New
detections go straight into SQLite via ``add_notification``.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

from configs.paths import NOTIFICATIONS_DIR
from src.api.db.database import get_connection, init_db
from src.api.time_utils import istanbul_now

logger = logging.getLogger(__name__)

_MAX_NOTIFICATIONS = 200
_THROTTLE_SECONDS = 10.0

_notifications: list[dict] = []
_lock = threading.Lock()

# Legacy JSONL path — kept for backward compatibility and a one-time
# migration import. New alerts are NOT appended to this file; SQLite is
# the source of truth.
ALERTS_LOG_PATH = NOTIFICATIONS_DIR / "alerts.jsonl"
_alerts_log_lock = threading.Lock()

# Legacy sidecar path — read once during the migration to preserve
# read-state for already-imported alerts. Not written to going forward.
ALERTS_READ_STATE_PATH = NOTIFICATIONS_DIR / "alerts_read_state.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_dir() -> Path:
    NOTIFICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return NOTIFICATIONS_DIR


def _last_time_for_source(source: str) -> float:
    with _lock:
        for n in reversed(_notifications):
            if n["source"] == source:
                return n["timestamp"]
    return 0.0


def should_notify(source: str, now: float | None = None) -> bool:
    """True if at least _THROTTLE_SECONDS have passed since the last
    notification from this source."""
    now = now if now is not None else time.time()
    return (now - _last_time_for_source(source)) > _THROTTLE_SECONDS


def _sanitize_detections(detections: list[dict]) -> list[dict]:
    """Coerce detections into a compact, JSON-safe shape."""
    clean: list[dict] = []
    for d in detections or []:
        try:
            conf = float(d.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        bbox_raw = d.get("bbox") or []
        try:
            bbox = [float(v) for v in bbox_raw][:4]
        except (TypeError, ValueError):
            bbox = []
        if len(bbox) != 4:
            bbox = []
        clean.append(
            {
                "label": str(d.get("label") or "fire"),
                "confidence": conf,
                "bbox": bbox,
            }
        )
    return clean


def _row_to_alert(row: sqlite3.Row) -> dict:
    """Render a ``detection_alerts`` row in the JSON shape the frontend
    expects (a superset of the ring-buffer entry plus read state)."""
    detections = []
    if row["detections_json"]:
        try:
            detections = json.loads(row["detections_json"])
        except (TypeError, ValueError):
            detections = []
    snapshot_ready, snapshot_version = _snapshot_status(row["snapshot_path"])
    return {
        "id": row["alert_id"],
        "source": row["source"],
        "timestamp": row["timestamp_epoch"],
        # ``time_str`` is the human-readable Istanbul time the existing
        # Detection Alerts tab + alert banner already render. We keep
        # the legacy ``YYYY-MM-DD HH:MM:SS`` shape; ``timestamp_iso``
        # is also exposed as the canonical machine-readable form.
        "time_str": row["timestamp_iso"][:19].replace("T", " ")
        if row["timestamp_iso"]
        else None,
        "timestamp_iso": row["timestamp_iso"],
        "detection_count": row["detection_count"] or 0,
        "max_confidence": row["confidence"] or 0.0,
        "label": row["label"],
        "image": row["snapshot_path"],
        "snapshot_path": row["snapshot_path"],
        "snapshot_ready": snapshot_ready,
        "snapshot_version": snapshot_version,
        "severity": row["severity"],
        "message": row["message"],
        "camera_id": row["camera_id"],
        "detections": detections,
        "is_read": int(row["is_read"] or 0),
        "read": bool(row["is_read"]),
        "read_at": row["read_at"],
    }


def _ring_entry_from_alert(alert: dict) -> dict:
    """Project a full alert dict down to the legacy ring-buffer shape
    so ``GET /monitoring/notifications`` keeps its historical contract."""
    return {
        "id": alert.get("id"),
        "source": alert.get("source"),
        "timestamp": alert.get("timestamp"),
        "time_str": alert.get("time_str"),
        "detection_count": alert.get("detection_count", 0),
        "max_confidence": alert.get("max_confidence", 0.0),
        "image": alert.get("image"),
    }


def _severity_for(label: str, confidence: float) -> str:
    """Best-effort severity tag for the ``severity`` column.

    Used by the dashboard if it ever wants a colour-coded chip on the
    Detection Alerts tab. Currently unused by the UI but cheap to
    populate so future surfaces can read it without a migration.
    """
    if confidence >= 0.75:
        return "critical"
    if confidence >= 0.5:
        return "warning"
    return "info"


def _snapshot_file_for(snapshot_path: str | None) -> Path | None:
    """Resolve a public static snapshot URL to its local file."""
    if not snapshot_path:
        return None
    prefix = "/static/notifications/"
    if not snapshot_path.startswith(prefix):
        return None
    filename = Path(snapshot_path).name
    if not filename:
        return None
    return NOTIFICATIONS_DIR / filename


def _snapshot_status(snapshot_path: str | None) -> tuple[bool, int | None]:
    """Return whether a snapshot exists and a cache-busting mtime token."""
    path = _snapshot_file_for(snapshot_path)
    if path is None:
        return False, None
    try:
        stat = path.stat()
    except OSError:
        return False, None
    return stat.st_size > 0, int(stat.st_mtime)


# ---------------------------------------------------------------------------
# Write path — the public entry point detection threads call.
# ---------------------------------------------------------------------------


def add_notification(
    source: str,
    detections: list[dict],
    image_path: str | None = None,
) -> dict:
    """Append a notification entry to SQLite + the in-memory ring buffer.

    ``image_path`` is the relative URL under
    ``/static/notifications/...`` (or ``None`` for synthetic alerts).
    The returned dict carries the full Detection Alert shape — ready to
    feed the frontend banner, the Detection Alerts tab row, and the
    alert summary tile.
    """
    init_db()  # idempotent — guarantees detection_alerts exists.
    now = time.time()
    clean_dets = _sanitize_detections(detections)

    iso = istanbul_now().isoformat()
    label = (clean_dets[0]["label"] if clean_dets else "fire") or "fire"
    max_conf = max((d["confidence"] for d in clean_dets), default=0.0)
    alert_id = str(time.time_ns())

    raw_payload = {
        "id": alert_id,
        "source": source,
        "timestamp": now,
        "time_str": iso[:19].replace("T", " "),
        "timestamp_iso": iso,
        "detection_count": len(clean_dets),
        "max_confidence": max_conf,
        "image": image_path,
        "detections": clean_dets,
    }

    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO detection_alerts (
                   alert_id, timestamp_iso, timestamp_epoch,
                   label, confidence, source, camera_id, severity,
                   message, snapshot_path, is_read, read_at,
                   detection_count, detections_json, raw_payload_json
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                alert_id,
                iso,
                now,
                label,
                max_conf,
                source,
                source,  # camera_id mirrors source for now
                _severity_for(label, max_conf),
                f"{label} detected on {source} at {max_conf*100:.1f}% confidence",
                image_path,
                0,           # is_read
                None,        # read_at
                len(clean_dets),
                json.dumps(clean_dets, ensure_ascii=False),
                json.dumps(raw_payload, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    ring_entry = {
        "id": alert_id,
        "source": source,
        "timestamp": now,
        "time_str": raw_payload["time_str"],
        "detection_count": len(clean_dets),
        "max_confidence": max_conf,
        "image": image_path,
    }
    with _lock:
        _notifications.append(ring_entry)
        if len(_notifications) > _MAX_NOTIFICATIONS:
            del _notifications[: len(_notifications) - _MAX_NOTIFICATIONS]

    snapshot_ready, snapshot_version = _snapshot_status(image_path)
    return {
        **raw_payload,
        "label": label,
        "snapshot_path": image_path,
        "snapshot_ready": snapshot_ready,
        "snapshot_version": snapshot_version,
        "severity": _severity_for(label, max_conf),
        "camera_id": source,
        "message": f"{label} detected on {source} at {max_conf*100:.1f}% confidence",
        "is_read": 0,
        "read": False,
        "read_at": None,
    }


def save_snapshot(source: str, frame_bgr) -> str | None:
    """Write a snapshot to disk under ``data/notifications/`` and return
    the relative static URL. Returns None on failure. Never raises."""
    try:
        import cv2  # local import keeps module importable without opencv
    except ImportError:
        logger.warning("opencv-python not installed; cannot save snapshot")
        return None
    try:
        out_dir = _ensure_dir()
        ts = istanbul_now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{source}_{ts}.jpg"
        filepath = out_dir / filename
        ok = cv2.imwrite(str(filepath), frame_bgr)
        if not ok:
            logger.warning("OpenCV failed to write snapshot: %s", filepath)
            return None
        return f"/static/notifications/{filename}"
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to save snapshot: %s", e)
        return None


# ---------------------------------------------------------------------------
# Read path — endpoints + ring-buffer feed.
# ---------------------------------------------------------------------------


def get_notifications(limit: int = 50) -> list[dict]:
    """Return the most recent notifications, newest first."""
    with _lock:
        snap = list(_notifications[-limit:])
    return list(reversed(snap))


def list_alerts(
    limit: int = 100,
    offset: int = 0,
    source: str | None = None,
    read_filter: str | None = None,
) -> list[dict]:
    """Return alerts from SQLite, **newest first**.

    Optional filters:
      - ``source`` — drone / webcam / pc_camera / demo
      - ``read_filter`` — "all" (default), "unread", "read"
    """
    init_db()
    where: list[str] = []
    params: list[object] = []
    if source:
        where.append("source = ?")
        params.append(source)
    if read_filter:
        rf = read_filter.strip().lower()
        if rf == "unread":
            where.append("is_read = 0")
        elif rf == "read":
            where.append("is_read = 1")
        # any other value falls through unchanged.
    sql = "SELECT * FROM detection_alerts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY timestamp_epoch DESC, alert_id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_row_to_alert(r) for r in rows]


def get_alert_by_id(alert_id: str) -> dict | None:
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM detection_alerts WHERE alert_id = ?",
            (str(alert_id),),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_alert(row) if row else None


def latest_alert() -> dict | None:
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM detection_alerts "
            "ORDER BY timestamp_epoch DESC, alert_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return _row_to_alert(row) if row else None


def alerts_summary() -> dict:
    """Aggregate stats over the SQLite alert log."""
    init_db()
    conn = get_connection()
    try:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM detection_alerts"
        ).fetchone()["n"]
        if total == 0:
            return {
                "total": 0,
                "unread_count": 0,
                "read_count": 0,
                "by_source": {},
                "max_confidence": None,
                "last_time_str": None,
                "last_source": None,
                "last_by_source": {},
                "latest_alert": None,
            }
        by_source_rows = conn.execute(
            "SELECT source, COUNT(*) AS n FROM detection_alerts GROUP BY source"
        ).fetchall()
        by_source = {r["source"]: r["n"] for r in by_source_rows}

        unread_count = conn.execute(
            "SELECT COUNT(*) AS n FROM detection_alerts WHERE is_read = 0"
        ).fetchone()["n"]

        max_conf_row = conn.execute(
            "SELECT MAX(confidence) AS m FROM detection_alerts"
        ).fetchone()
        max_conf = max_conf_row["m"] or 0.0

        last_row = conn.execute(
            "SELECT * FROM detection_alerts "
            "ORDER BY timestamp_epoch DESC, alert_id DESC LIMIT 1"
        ).fetchone()
        last_alert = _row_to_alert(last_row) if last_row else None

        # Per-source "last seen" timestamps: cheap and portable to do
        # one targeted query per distinct source rather than one big
        # window-function query. ``by_source`` already enumerates the
        # distinct sources for us.
        last_by_source: dict[str, str] = {}
        for src in by_source:
            r = conn.execute(
                "SELECT timestamp_iso FROM detection_alerts "
                "WHERE source = ? "
                "ORDER BY timestamp_epoch DESC LIMIT 1",
                (src,),
            ).fetchone()
            if r and r["timestamp_iso"]:
                last_by_source[src] = (
                    r["timestamp_iso"][:19].replace("T", " ")
                )
    finally:
        conn.close()

    return {
        "total": total,
        "unread_count": unread_count,
        "read_count": total - unread_count,
        "by_source": by_source,
        "max_confidence": max_conf,
        "last_time_str": last_alert["time_str"] if last_alert else None,
        "last_source": last_alert["source"] if last_alert else None,
        "last_by_source": last_by_source,
        "latest_alert": last_alert,
    }


def mark_alert_read(alert_id: str) -> dict | None:
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT alert_id FROM detection_alerts WHERE alert_id = ?",
            (str(alert_id),),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE detection_alerts "
            "SET is_read = 1, read_at = COALESCE(read_at, ?) "
            "WHERE alert_id = ?",
            (istanbul_now().isoformat(), str(alert_id)),
        )
        conn.commit()
    finally:
        conn.close()
    return get_alert_by_id(alert_id)


def mark_alert_unread(alert_id: str) -> dict | None:
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT alert_id FROM detection_alerts WHERE alert_id = ?",
            (str(alert_id),),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE detection_alerts SET is_read = 0, read_at = NULL "
            "WHERE alert_id = ?",
            (str(alert_id),),
        )
        conn.commit()
    finally:
        conn.close()
    return get_alert_by_id(alert_id)


def mark_all_alerts_read() -> int:
    """Flip every currently-unread alert to read. Returns the count."""
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE detection_alerts SET is_read = 1, read_at = ? "
            "WHERE is_read = 0",
            (istanbul_now().isoformat(),),
        )
        conn.commit()
        return cur.rowcount or 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Demo + test helpers
# ---------------------------------------------------------------------------


def add_demo_alert(
    label: str = "fire",
    confidence: float = 0.78,
    source: str = "demo",
) -> dict:
    """Append a synthetic alert through the real persistence path.

    Backs ``POST /monitoring/alerts/test``. Persists into SQLite the
    same way a real YOLO detection does, so the Detection Alerts tab,
    the in-app banner, and ``/alerts/summary`` all light up correctly
    when no camera hardware is available.
    """
    label_clean = (label or "fire").strip().lower()
    if label_clean not in ("fire", "smoke"):
        label_clean = "fire"
    try:
        confidence_clean = float(confidence)
    except (TypeError, ValueError):
        confidence_clean = 0.78
    confidence_clean = max(0.0, min(1.0, confidence_clean))

    return add_notification(
        source=source,
        detections=[
            {
                "label": label_clean,
                "confidence": confidence_clean,
                "bbox": [240, 200, 400, 360],
            }
        ],
        image_path=None,
    )


def clear_notifications() -> int:
    """Wipe alerts for tests. Returns the number cleared.

    Truncates the SQLite alert table and the in-memory ring buffer.
    The legacy JSONL file and read-state sidecar are also removed so a
    test starts from a known-clean baseline.
    """
    init_db()
    conn = get_connection()
    try:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM detection_alerts"
        ).fetchone()["n"]
        conn.execute("DELETE FROM detection_alerts")
        conn.commit()
    finally:
        conn.close()
    with _lock:
        _notifications.clear()
    with _alerts_log_lock:
        try:
            if ALERTS_LOG_PATH.exists():
                ALERTS_LOG_PATH.unlink()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to clear legacy JSONL: %s", e)
        try:
            if ALERTS_READ_STATE_PATH.exists():
                ALERTS_READ_STATE_PATH.unlink()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to clear legacy sidecar: %s", e)
    return n


# ---------------------------------------------------------------------------
# Migration: import legacy JSONL into SQLite (idempotent).
# ---------------------------------------------------------------------------


def _read_legacy_jsonl() -> list[dict]:
    if not ALERTS_LOG_PATH.exists():
        return []
    out: list[dict] = []
    try:
        with ALERTS_LOG_PATH.open("r", encoding="utf-8") as fh:
            for i, raw in enumerate(fh):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(json.loads(raw))
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping corrupt JSONL line %d during import", i + 1
                    )
                    continue
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to read legacy JSONL: %s", e)
    return out


def _read_legacy_sidecar() -> dict[str, str]:
    if not ALERTS_READ_STATE_PATH.exists():
        return {}
    try:
        raw = ALERTS_READ_STATE_PATH.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        return {str(k): (str(v) if v else "") for k, v in data.items() if v}
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not read legacy sidecar: %s", e)
        return {}


def import_legacy_jsonl() -> int:
    """Idempotently import legacy alerts.jsonl rows into SQLite.

    Each JSONL entry is inserted into ``detection_alerts`` only if its
    ``id`` is not already present. Read-state from the legacy
    ``alerts_read_state.json`` sidecar is preserved for imported rows.
    Returns the number of newly-inserted alerts.
    """
    init_db()
    legacy = _read_legacy_jsonl()
    if not legacy:
        return 0
    sidecar = _read_legacy_sidecar()

    conn = get_connection()
    inserted = 0
    try:
        existing = {
            r["alert_id"]
            for r in conn.execute(
                "SELECT alert_id FROM detection_alerts"
            ).fetchall()
        }
        for entry in legacy:
            aid = str(entry.get("id") or "")
            if not aid or aid in existing:
                continue
            ts_epoch = entry.get("timestamp")
            try:
                ts_epoch = float(ts_epoch) if ts_epoch is not None else 0.0
            except (TypeError, ValueError):
                ts_epoch = 0.0
            time_str = entry.get("time_str") or ""
            # Reconstruct an Istanbul-like ISO if only the legacy
            # "YYYY-MM-DD HH:MM:SS" form is present.
            iso = (
                time_str.replace(" ", "T") + "+03:00" if time_str else ""
            )
            detections = entry.get("detections") or []
            try:
                max_conf = float(entry.get("max_confidence") or 0.0)
            except (TypeError, ValueError):
                max_conf = 0.0
            label = (
                detections[0].get("label", "fire") if detections else "fire"
            )
            source = str(entry.get("source") or "unknown")
            snapshot = entry.get("image")
            is_read = 1 if aid in sidecar else 0
            read_at = sidecar.get(aid) or None
            conn.execute(
                """INSERT OR IGNORE INTO detection_alerts (
                       alert_id, timestamp_iso, timestamp_epoch,
                       label, confidence, source, camera_id, severity,
                       message, snapshot_path, is_read, read_at,
                       detection_count, detections_json, raw_payload_json
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    aid,
                    iso,
                    ts_epoch,
                    label,
                    max_conf,
                    source,
                    source,
                    _severity_for(label, max_conf),
                    f"{label} detected on {source} at {max_conf*100:.1f}% confidence",
                    snapshot,
                    is_read,
                    read_at,
                    int(entry.get("detection_count") or len(detections)),
                    json.dumps(detections, ensure_ascii=False),
                    json.dumps(entry, ensure_ascii=False, default=str),
                ),
            )
            inserted += 1
        conn.commit()
    finally:
        conn.close()
    if inserted:
        logger.info(
            "Imported %d legacy JSONL alert(s) into detection_alerts table.",
            inserted,
        )
    return inserted


def hydrate_ring_buffer_from_log(limit: int = _MAX_NOTIFICATIONS) -> int:
    """Rehydrate the in-memory ring buffer from SQLite at startup.

    Also runs the idempotent JSONL→SQLite import so a backend that
    boots into a fresh DB still picks up legacy alerts. Returns the
    number of entries loaded into the ring buffer.
    """
    try:
        import_legacy_jsonl()
    except Exception as e:  # noqa: BLE001
        # Migration is best-effort — a corrupt JSONL must never block
        # backend boot.
        logger.warning("Legacy JSONL import skipped: %s", e)

    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM detection_alerts "
            "ORDER BY timestamp_epoch ASC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return 0
    with _lock:
        _notifications.clear()
        for r in rows:
            _notifications.append(_ring_entry_from_alert(_row_to_alert(r)))
    return len(rows)
