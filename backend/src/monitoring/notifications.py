"""In-memory + on-disk fire-detection notifications.

This is the *only* place monitoring writes observations. Notifications are
strictly separated from ``run_history`` (the Option 3 prediction audit
log) and never modify ``predicted_fwi`` or ``high_risk_flag``. They are
an operational alerting channel, not a data source for the model.

Two-tier storage
----------------
1. **Ring buffer** — up to ``_MAX_NOTIFICATIONS`` most recent alerts held
   in memory for the live Monitoring feed. Same shape as before (id,
   source, timestamp, time_str, detection_count, max_confidence, image).
2. **Append-only JSONL evidence log** — every alert is also appended to
   ``data/notifications/alerts.jsonl`` with the **full per-detection
   list** (label, confidence, bbox). This is the durable evidence trail
   the Detection Alerts tab reads from, and it survives restarts. Any
   mid-write crash loses at most the partially written trailing line,
   which the JSONL reader skips.

The snapshots themselves are already written as JPEG files to
``data/notifications/`` by ``save_snapshot()`` and served via the
``/static/notifications/`` static mount.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from configs.paths import NOTIFICATIONS_DIR
from src.api.time_utils import istanbul_now

logger = logging.getLogger(__name__)

_MAX_NOTIFICATIONS = 200
_THROTTLE_SECONDS = 10.0

_notifications: list[dict] = []
_lock = threading.Lock()

# Evidence log — one JSON object per line, append-only, lock-protected.
# Lives next to the snapshot JPEGs so a single directory backup captures
# both the metadata trail and the frames it references.
ALERTS_LOG_PATH = NOTIFICATIONS_DIR / "alerts.jsonl"
_alerts_log_lock = threading.Lock()

# Sidecar JSON file holding the read-state map for the JSONL evidence
# log. Why a sidecar and not an extra column in the JSONL itself:
# the JSONL is append-only and never edited in place — a "mark as read"
# would otherwise force a full file rewrite. The sidecar is small
# (one bool per alert id) and is rewritten atomically via a temp file
# + os.replace, so a crash mid-write cannot leave it in a half-state.
# A missing sidecar means "every alert is unread by default", which
# matches the natural semantics for a fresh clone or a freshly
# truncated evidence log.
ALERTS_READ_STATE_PATH = NOTIFICATIONS_DIR / "alerts_read_state.json"
_read_state_lock = threading.Lock()


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
    """True if at least _THROTTLE_SECONDS have passed since the last notification
    from this source."""
    now = now if now is not None else time.time()
    return (now - _last_time_for_source(source)) > _THROTTLE_SECONDS


def _sanitize_detections(detections: list[dict]) -> list[dict]:
    """Coerce detections into a compact, JSON-safe shape.

    Drops None/NaN confidences and non-numeric bbox components so the
    JSONL log stays strictly machine-readable. Unknown labels collapse
    to ``"fire"`` (the only class the current YOLO detector emits).
    """
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


def _append_alert_log(entry: dict) -> None:
    """Append a single alert entry to the JSONL evidence log.

    Never raises — a failed evidence write must not take the monitoring
    loop down. It logs and moves on; the in-memory ring buffer still has
    the entry so the live Monitoring feed is unaffected.
    """
    try:
        _ensure_dir()
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with _alerts_log_lock:
            with ALERTS_LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to append alert to evidence log: %s", e)


def add_notification(
    source: str,
    detections: list[dict],
    image_path: str | None = None,
) -> dict:
    """Append a notification entry to the ring buffer **and** the JSONL
    evidence log.

    ``image_path`` is the relative URL under ``/static/notifications/...``.

    The ring-buffer entry keeps its historical shape (``detection_count``
    + ``max_confidence``) so existing callers — notably the live
    ``/monitoring/notifications`` feed on the Monitoring tab — see no
    change. The evidence log entry additionally carries the full
    per-detection list (with bboxes) for the Detection Alerts tab.
    """
    now = time.time()
    clean_dets = _sanitize_detections(detections)

    entry = {
        "id": str(int(now * 1000)),
        "source": source,
        "timestamp": now,
        # Always Istanbul-local, independent of the host OS timezone —
        # otherwise a UTC-container host would show detection times three
        # hours behind Karabük reality.
        "time_str": istanbul_now().strftime("%Y-%m-%d %H:%M:%S"),
        "detection_count": len(clean_dets),
        "max_confidence": max(
            (d["confidence"] for d in clean_dets), default=0.0
        ),
        "image": image_path,
    }
    with _lock:
        _notifications.append(entry)
        if len(_notifications) > _MAX_NOTIFICATIONS:
            del _notifications[: len(_notifications) - _MAX_NOTIFICATIONS]

    # Evidence log carries the strictly-richer shape: same fields as the
    # ring-buffer entry plus the per-detection list.
    alert_entry = {**entry, "detections": clean_dets}
    _append_alert_log(alert_entry)
    # The caller — POST /monitoring/alerts/test, the YOLO inference loop,
    # the demo seed script — wants a payload it can use as-is for the
    # Detection Alerts tab. New alerts are unread by definition.
    return {**alert_entry, "read": False, "read_at": None}


def save_snapshot(source: str, frame_bgr) -> str | None:
    """Write a snapshot to disk under ``data/notifications/`` and return the
    relative static URL (``/static/notifications/<filename>``). Returns None
    on failure (opencv missing, write error, etc.). Never raises."""
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
        cv2.imwrite(str(filepath), frame_bgr)
        return f"/static/notifications/{filename}"
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to save snapshot: %s", e)
        return None


def get_notifications(limit: int = 50) -> list[dict]:
    """Return the most recent notifications, newest first."""
    with _lock:
        snap = list(_notifications[-limit:])
    return list(reversed(snap))


def clear_notifications() -> int:
    """Clear all notifications. Returns the number cleared. Test helper.

    Also truncates the on-disk evidence log so tests that rely on a
    known-empty baseline start from zero. Production code never calls
    this — the evidence log is append-only during normal operation.
    """
    with _lock:
        n = len(_notifications)
        _notifications.clear()
    with _alerts_log_lock:
        try:
            if ALERTS_LOG_PATH.exists():
                ALERTS_LOG_PATH.unlink()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to clear evidence log: %s", e)
    # Drop the sidecar too so the next test starts with a clean
    # everything-is-unread baseline.
    with _read_state_lock:
        try:
            if ALERTS_READ_STATE_PATH.exists():
                ALERTS_READ_STATE_PATH.unlink()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to clear read-state sidecar: %s", e)
    return n


# ---------------------------------------------------------------------------
# Evidence log — durable alert history for the Detection Alerts tab.
# ---------------------------------------------------------------------------


def _read_alert_log() -> list[dict]:
    """Read every alert from the JSONL evidence log, oldest first.

    Tolerates partial / corrupt trailing lines (skipped with a warning)
    so a mid-write crash cannot break the reader.
    """
    if not ALERTS_LOG_PATH.exists():
        return []
    out: list[dict] = []
    with _alerts_log_lock:
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
                            "Skipping corrupt alert log line %d", i + 1
                        )
                        continue
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to read alert evidence log: %s", e)
    return out


# ---------------------------------------------------------------------------
# Read / unread sidecar — Option A persistence (see module docstring above).
# ---------------------------------------------------------------------------


def _read_state_load() -> dict[str, str]:
    """Load the alert-id → ISO-timestamp map from the sidecar file.

    Missing/corrupt file → empty dict (everything unread). Never
    raises — read state is a best-effort UX nicety, the JSONL log is
    the source of truth for "which alerts exist".
    """
    if not ALERTS_READ_STATE_PATH.exists():
        return {}
    try:
        raw = ALERTS_READ_STATE_PATH.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        # Coerce keys to str and drop non-truthy values so old entries
        # written as bools still round-trip cleanly.
        return {str(k): (str(v) if v else "") for k, v in data.items() if v}
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not read alerts_read_state.json: %s", e)
        return {}


def _read_state_save(state: dict[str, str]) -> None:
    """Atomically rewrite the sidecar file (temp + os.replace).

    Holds ``_read_state_lock`` for the rewrite. Never raises — if the
    write fails, the in-memory call still returns and the next call
    will try again.
    """
    try:
        _ensure_dir()
        tmp = ALERTS_READ_STATE_PATH.with_suffix(".json.tmp")
        body = json.dumps(state, ensure_ascii=False, sort_keys=True)
        with _read_state_lock:
            with tmp.open("w", encoding="utf-8") as fh:
                fh.write(body)
            os.replace(tmp, ALERTS_READ_STATE_PATH)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not write alerts_read_state.json: %s", e)


def _annotate_read(alert: dict, read_state: dict[str, str]) -> dict:
    """Return a shallow copy of ``alert`` with read/read_at filled in.

    ``read`` is True iff the alert id appears in the sidecar map, and
    ``read_at`` carries the timestamp the alert was marked read (or
    None for unread alerts).
    """
    aid = str(alert.get("id"))
    read_at = read_state.get(aid) or None
    return {**alert, "read": read_at is not None, "read_at": read_at}


def mark_alert_read(alert_id: str) -> dict | None:
    """Mark a single alert as read. Returns the updated alert or None
    if the id doesn't exist in the evidence log."""
    alert = get_alert_by_id(alert_id)
    if alert is None:
        return None
    state = _read_state_load()
    state[str(alert_id)] = istanbul_now().isoformat()
    _read_state_save(state)
    return _annotate_read(alert, state)


def mark_alert_unread(alert_id: str) -> dict | None:
    """Mark a single alert as unread. No-op if it wasn't marked read."""
    alert = get_alert_by_id(alert_id)
    if alert is None:
        return None
    state = _read_state_load()
    state.pop(str(alert_id), None)
    _read_state_save(state)
    return _annotate_read(alert, state)


def mark_all_alerts_read() -> int:
    """Mark every alert currently in the evidence log as read.

    Returns the number of alerts that were *previously unread* and
    have now been flipped — so the caller can show "Marked N alert(s)
    as read." The JSONL file is not touched.
    """
    alerts = _read_alert_log()
    state = _read_state_load()
    now = istanbul_now().isoformat()
    flipped = 0
    for a in alerts:
        aid = str(a.get("id"))
        if not aid:
            continue
        if aid not in state:
            state[aid] = now
            flipped += 1
    if flipped:
        _read_state_save(state)
    return flipped


def list_alerts(
    limit: int = 100,
    offset: int = 0,
    source: str | None = None,
    read_filter: str | None = None,
) -> list[dict]:
    """Return alerts from the evidence log, **newest first**.

    Supports two optional filters:

    - ``source`` — ``drone`` / ``webcam`` / ``pc_camera`` / ``demo``.
    - ``read_filter`` — ``"all"`` (default), ``"unread"``, ``"read"``.

    Every returned entry is annotated with ``read`` (bool) and
    ``read_at`` (ISO 8601 or ``None``) drawn from the sidecar
    read-state map, so the frontend never has to ask twice.
    """
    alerts = _read_alert_log()
    if source:
        alerts = [a for a in alerts if a.get("source") == source]

    state = _read_state_load()
    annotated = [_annotate_read(a, state) for a in alerts]

    if read_filter:
        rf = read_filter.strip().lower()
        if rf == "unread":
            annotated = [a for a in annotated if not a["read"]]
        elif rf == "read":
            annotated = [a for a in annotated if a["read"]]
        # any other value, including "all", falls through unchanged.

    annotated.reverse()  # newest first
    return annotated[offset : offset + limit]


def get_alert_by_id(alert_id: str) -> dict | None:
    """Return a single alert by id (string), or None if not found.

    The returned dict carries the read/read_at annotation just like
    ``list_alerts``."""
    state = _read_state_load()
    for a in _read_alert_log():
        if str(a.get("id")) == str(alert_id):
            return _annotate_read(a, state)
    return None


def latest_alert() -> dict | None:
    """Return the most recently appended alert from the evidence log, or None.

    Backs the ``GET /monitoring/alerts/latest`` endpoint, which the
    dashboard polls every few seconds to surface a visible in-app
    banner the moment a new fire detection lands. Reads the evidence
    log fresh on each call — the JSONL file is small (one line per
    alert, append-only) so this is cheap, and it means we never miss
    an alert written by another process or a background detection
    thread.
    """
    alerts = _read_alert_log()
    if not alerts:
        return None
    state = _read_state_load()
    return _annotate_read(alerts[-1], state)


def add_demo_alert(
    label: str = "fire",
    confidence: float = 0.78,
    source: str = "demo",
) -> dict:
    """Append a synthetic alert for UI / smoke-test purposes.

    Backs the ``POST /monitoring/alerts/test`` endpoint, which is
    invaluable when no camera or drone hardware is available — a
    collaborator (or a CI smoke test) can trigger a real evidence-log
    write and confirm that the Detection Alerts tab, the dashboard
    notification banner, and the alert summary tiles all light up
    correctly.

    The entry goes through the same code path as a real detection
    (``add_notification`` writes to the ring buffer AND the JSONL
    evidence log), so demo alerts persist across restarts exactly
    like real ones. They are tagged ``source="demo"`` (or whatever
    the caller passes) so they are easy to filter or remove later.
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
                # Centred placeholder bbox (no real frame to crop from).
                "bbox": [240, 200, 400, 360],
            }
        ],
        image_path=None,
    )


def alerts_summary() -> dict:
    """Aggregate stats over the full evidence log.

    Returns totals, by-source counts, the highest confidence ever
    recorded, and the most-recently-appended alert's source + time_str.
    The evidence log is append-only, so "last" is unambiguously the last
    line in the file — we do not compare timestamps (Windows
    ``time.time()`` has ~15 ms resolution so two quick calls can land on
    the same millisecond and break ordering).
    """
    alerts = _read_alert_log()
    total = len(alerts)
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
        }

    state = _read_state_load()

    by_source: dict[str, int] = {}
    max_conf = 0.0
    last_by_source: dict[str, str] = {}
    unread_count = 0

    for a in alerts:
        src = str(a.get("source") or "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        try:
            conf = float(a.get("max_confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf > max_conf:
            max_conf = conf
        # Evidence log is append-ordered; overwriting is fine.
        ts_str = a.get("time_str") or ""
        if ts_str:
            last_by_source[src] = ts_str
        if str(a.get("id")) not in state:
            unread_count += 1

    last = alerts[-1]
    return {
        "total": total,
        "unread_count": unread_count,
        "read_count": total - unread_count,
        "by_source": by_source,
        "max_confidence": max_conf,
        "last_time_str": last.get("time_str"),
        "last_source": str(last.get("source") or "unknown"),
        "last_by_source": last_by_source,
    }


def hydrate_ring_buffer_from_log(limit: int = _MAX_NOTIFICATIONS) -> int:
    """Rehydrate the in-memory ring buffer from the JSONL log.

    Called once at backend startup so the live Monitoring feed does not
    appear empty after a restart — the most recent alerts from disk are
    loaded back into the ring buffer with their original shape.
    Returns the number of entries loaded.
    """
    alerts = _read_alert_log()
    if not alerts:
        return 0
    # Keep only the trailing ``limit`` so we don't overflow the buffer.
    tail = alerts[-limit:]
    with _lock:
        _notifications.clear()
        for a in tail:
            _notifications.append(
                {
                    "id": a.get("id"),
                    "source": a.get("source"),
                    "timestamp": a.get("timestamp"),
                    "time_str": a.get("time_str"),
                    "detection_count": a.get("detection_count", 0),
                    "max_confidence": a.get("max_confidence", 0.0),
                    "image": a.get("image"),
                }
            )
    return len(tail)
