"""Shared YOLO fire detector — lazy, thread-safe singleton.

Used by both camera and drone loops. Loaded from
``models/fire_detection/best.pt`` (migrated from the legacy detection
reference). This module never reads anything from the Option 3 prediction
pipeline — it is a detection-only asset.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

from configs.paths import FIRE_DETECTION_MODEL_PATH

logger = logging.getLogger(__name__)

_model: Any | None = None
_model_lock = threading.Lock()
_load_failed = False


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Tunable without code changes. Lowering imgsz from 640 → 416 on CPU
# roughly halves inference time at a small recall cost; operators can
# experiment without restart-recompile.
YOLO_IMG_SIZE = _env_int("MONITORING_YOLO_IMGSZ", 640)
YOLO_CONF = _env_float("MONITORING_YOLO_CONF", 0.4)

_LABEL_ALIASES = {
    "fire": "fire",
    "flame": "fire",
    "flames": "fire",
    "smoke": "smoke",
}


def normalize_detection_label(label: Any) -> str:
    """Return the canonical label stored by overlays and alerts."""
    clean = str(label or "unknown").strip().lower()
    if not clean:
        return "unknown"
    return _LABEL_ALIASES.get(clean, clean)


def get_detector() -> Any | None:
    """Return the loaded YOLO model or None if unavailable.

    A ``None`` return means frames will flow through without detection
    (e.g. ultralytics not installed, weights missing, or GPU/CPU init failed).
    Callers must handle ``None`` gracefully — detection is optional; the
    raw camera stream must still work.
    """
    global _model, _load_failed

    if _model is not None:
        return _model
    if _load_failed:
        return None

    with _model_lock:
        if _model is not None:
            return _model
        if _load_failed:
            return None

        if not FIRE_DETECTION_MODEL_PATH.exists():
            logger.warning(
                "YOLO fire-detection weights not found at %s — detection disabled",
                FIRE_DETECTION_MODEL_PATH,
            )
            _load_failed = True
            return None

        try:
            from ultralytics import YOLO
        except ImportError as e:
            logger.warning("ultralytics not installed: %s — detection disabled", e)
            _load_failed = True
            return None

        try:
            _model = YOLO(str(FIRE_DETECTION_MODEL_PATH))
            logger.info("YOLO fire detector loaded from %s", FIRE_DETECTION_MODEL_PATH)
            return _model
        except Exception as e:  # noqa: BLE001 — detection must not crash the API
            logger.exception("Failed to load YOLO model: %s", e)
            _load_failed = True
            return None


def run_detection(frame) -> list[dict]:
    """Run YOLO on a single frame and return a list of detection dicts.

    Each detection is ``{"label": str, "confidence": float, "bbox": [x1,y1,x2,y2]}``.
    Returns ``[]`` if detection is unavailable or the model found nothing.
    """
    model = get_detector()
    if model is None:
        return []

    try:
        results = model.predict(
            frame, imgsz=YOLO_IMG_SIZE, conf=YOLO_CONF, verbose=False
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("YOLO prediction failed: %s", e)
        return []

    detections: list[dict] = []
    for r in results:
        boxes = getattr(r, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            try:
                conf = float(box.conf[0])
                bbox = [float(x) for x in box.xyxy[0].tolist()]
                cls_id = int(box.cls[0])
                label = normalize_detection_label(r.names.get(cls_id, "unknown"))
            except Exception:  # noqa: BLE001
                continue
            detections.append({"label": label, "confidence": conf, "bbox": bbox})
    return detections
