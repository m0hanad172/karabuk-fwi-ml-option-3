"""Persistent logical-role → device-index mapping for the monitoring layer.

The problem this module solves
------------------------------
The monitoring layer has two *logical* roles:

  - ``pc_camera`` → Built-in laptop camera
  - ``webcam``    → Logitech BRIO 100 (the dedicated project webcam)

OpenCV sees devices only by integer index. Those indices are **not
stable**:

  - They depend on USB enumeration order.
  - They shift when a device is unplugged / replugged.
  - They can reshuffle between backend restarts.

Without persistence, every fresh backend start resets the mapping to
``{pc_camera: 0, webcam: 1}`` defaults. An operator who fixed the
mapping yesterday would have to re-run auto-detect today.

What this module does
---------------------
  1. ``load_mapping()`` reads ``data/camera_mapping.json`` and returns
     a dict of ``{role → {"index": int, "fingerprint": {w, h, fps}}}``.
  2. ``save_mapping(cameras)`` serialises the current live CAMERAS dict,
     recording each camera's index + a lightweight fingerprint
     (width × height × fps) for later re-validation.
  3. ``apply_mapping(cameras)`` pushes the persisted indices back into
     the live CAMERAS dict at import / startup time.
  4. ``validate_mapping(cameras, discovered)`` compares the persisted
     fingerprint against what a fresh ``discover_devices`` probe sees
     and returns a list of roles whose fingerprint no longer matches.
     The startup hook in ``src/api/main.py`` uses this to detect
     "indices changed while the backend was off" and log a warning so
     the operator knows to re-run auto-detect.

Fingerprint rationale
---------------------
OpenCV on Windows does *not* expose a stable device name without extra
libraries (pygrabber / DirectShow COM). We use the resolution + FPS the
device reports as a cheap fingerprint: the BRIO reports 1920×1080 on
DSHOW, the built-in laptop camera typically reports 1280×720 or lower.
That's enough to detect "this index is now a different device".

This module is intentionally side-effect free on import. The caller
decides when to load, apply, save, and validate.

Monitoring stays strictly separate from the prediction pipeline — this
module never touches ``run_history`` or ``system_state``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from configs.paths import CAMERA_MAPPING_PATH

logger = logging.getLogger(__name__)


# Fingerprint tolerance — FPS reported by OpenCV is noisy, so we only
# require the integer part to match. Resolution is exact.
_FPS_TOLERANCE = 2.0


@dataclass
class Fingerprint:
    width: int
    height: int
    fps: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": int(self.width),
            "height": int(self.height),
            "fps": round(float(self.fps), 1),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Fingerprint":
        return cls(
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
            fps=float(d.get("fps", 0.0)),
        )

    def matches(self, other: "Fingerprint") -> bool:
        if self.width != other.width or self.height != other.height:
            return False
        return abs(self.fps - other.fps) <= _FPS_TOLERANCE


def _path() -> Path:
    return CAMERA_MAPPING_PATH


def mapping_file_exists() -> bool:
    """Return True if ``data/camera_mapping.json`` has been written.

    The startup hook in ``src/api/main.py`` uses this to distinguish
    "first boot, never mapped" (→ run auto-detect once so logical roles
    bind to the correct physical devices) from "already mapped on a
    previous boot" (→ only validate, never mutate).
    """
    return _path().exists()


def load_mapping() -> dict[str, dict[str, Any]]:
    """Return the persisted mapping, or an empty dict if no file exists.

    The on-disk shape is:

        {
          "version": 1,
          "roles": {
            "pc_camera": {"index": 0, "fingerprint": {...}},
            "webcam":    {"index": 1, "fingerprint": {...}}
          }
        }
    """
    p = _path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        # A corrupt mapping file must not crash the backend. Log + ignore.
        logger.warning("Camera mapping unreadable, ignoring: %s", e)
        return {}
    roles = raw.get("roles") if isinstance(raw, dict) else None
    if not isinstance(roles, dict):
        return {}
    return roles


def save_mapping(cameras: dict[str, Any]) -> None:
    """Persist the live CAMERAS dict to disk.

    ``cameras`` is expected to be the registry from ``cameras.py`` —
    ``{role → CameraState}``. We record the index and the most recent
    observed resolution / fps so ``validate_mapping`` can later detect
    whether the device at that index is still the same one.
    """
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "roles": {
            role: {
                "index": int(state.index),
                "fingerprint": _fingerprint_from_state(state).to_dict(),
            }
            for role, state in cameras.items()
        },
    }
    try:
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(
            "Saved camera mapping: %s",
            {role: entry["index"] for role, entry in payload["roles"].items()},
        )
    except OSError as e:
        logger.warning("Could not save camera mapping: %s", e)


def apply_mapping(cameras: dict[str, Any]) -> None:
    """Push persisted indices back onto the live CAMERAS dict.

    Called once at import time by ``cameras.py``. No-op if no mapping
    file exists (first run) or if a role in the file is not in the live
    registry (forward-compat safety).
    """
    persisted = load_mapping()
    if not persisted:
        return
    for role, entry in persisted.items():
        state = cameras.get(role)
        if state is None:
            continue
        try:
            new_index = int(entry.get("index"))
        except (TypeError, ValueError):
            continue
        state.index = new_index
    logger.info(
        "Applied persisted camera mapping: %s",
        {role: cameras[role].index for role in persisted if role in cameras},
    )


def validate_mapping(
    cameras: dict[str, Any],
    discovered: list[dict[str, Any]],
) -> list[str]:
    """Compare persisted fingerprints vs. a fresh ``discover_devices`` probe.

    Returns a list of role names whose persisted index either:
      - no longer opens, OR
      - opens but reports a fingerprint that doesn't match what was saved.

    Having this as a separate pure function means the API main lifespan
    hook can call it cheaply and log a warning, and a future endpoint
    can expose the result to the UI without changing any behaviour.
    """
    persisted = load_mapping()
    if not persisted:
        return []
    discovered_by_index = {int(d.get("index", -1)): d for d in discovered}

    stale: list[str] = []
    for role, entry in persisted.items():
        if role not in cameras:
            continue
        try:
            idx = int(entry.get("index"))
        except (TypeError, ValueError):
            continue
        fp_saved = Fingerprint.from_dict(entry.get("fingerprint") or {})
        probe = discovered_by_index.get(idx)
        if probe is None or not probe.get("opened", False):
            stale.append(role)
            continue
        fp_now = Fingerprint(
            width=int(probe.get("width", 0)),
            height=int(probe.get("height", 0)),
            fps=float(probe.get("fps", 0.0)),
        )
        if fp_saved.width and fp_saved.height and not fp_saved.matches(fp_now):
            stale.append(role)
    return stale


def _fingerprint_from_state(state: Any) -> Fingerprint:
    """Best-effort fingerprint extraction from a CameraState-like object.

    CameraState does not track width/height/fps directly (frames are raw
    ndarrays), so this function falls back to zeros if unavailable. The
    values are filled in by ``apply_discovered_fingerprint`` below
    whenever a fresh ``discover_devices`` result is available.
    """
    width = int(getattr(state, "width", 0) or 0)
    height = int(getattr(state, "height", 0) or 0)
    fps = float(getattr(state, "fps_reported", 0.0) or 0.0)
    return Fingerprint(width=width, height=height, fps=fps)


def apply_discovered_fingerprint(
    cameras: dict[str, Any],
    discovered: list[dict[str, Any]],
) -> None:
    """Attach width/height/fps from a fresh probe onto each CameraState.

    This lets ``save_mapping`` write a meaningful fingerprint without
    the CameraState dataclass having to own per-device probe data in
    its hot path.
    """
    by_index = {int(d.get("index", -1)): d for d in discovered}
    for state in cameras.values():
        probe = by_index.get(int(state.index))
        if not probe or not probe.get("opened", False):
            continue
        setattr(state, "width", int(probe.get("width", 0)))
        setattr(state, "height", int(probe.get("height", 0)))
        setattr(state, "fps_reported", float(probe.get("fps", 0.0)))
