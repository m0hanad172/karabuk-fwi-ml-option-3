"""Inspect the configured active fire/smoke YOLO detector.

This script is read-only: it does not write to SQLite and does not create
alerts. By default it loads `configs.paths.FIRE_DETECTION_MODEL_PATH`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from configs.paths import FIRE_DETECTION_MODEL_PATH  # noqa: E402
from src.monitoring.yolo_detector import (  # noqa: E402
    YOLO_CONF,
    YOLO_IMG_SIZE,
    normalize_detection_label,
)


def _load_image(path: Path):
    try:
        import cv2
    except ImportError as e:
        raise RuntimeError(f"opencv-python is required to read sample images: {e}") from e
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"Could not read sample image: {path}")
    return image


def _raw_detection_rows(results) -> list[dict]:
    rows: list[dict] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            try:
                cls_id = int(box.cls[0])
                raw_label = result.names.get(cls_id, "unknown")
                confidence = float(box.conf[0])
                bbox = [float(x) for x in box.xyxy[0].tolist()]
            except Exception:  # noqa: BLE001
                continue
            rows.append(
                {
                    "class_id": cls_id,
                    "raw_label": raw_label,
                    "normalized_label": normalize_detection_label(raw_label),
                    "confidence": round(confidence, 6),
                    "bbox": [round(v, 2) for v in bbox],
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        type=Path,
        default=FIRE_DETECTION_MODEL_PATH,
        help="YOLO model path. Defaults to configs.paths.FIRE_DETECTION_MODEL_PATH.",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Optional sample image for one read-only prediction pass.",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=YOLO_CONF,
        help="Confidence threshold for the sample prediction pass.",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=YOLO_IMG_SIZE,
        help="YOLO image size for the sample prediction pass.",
    )
    args = parser.parse_args()

    from ultralytics import YOLO

    model_path = args.model
    model = YOLO(str(model_path))
    model_names = dict(model.names)
    normalized_names = [
        normalize_detection_label(name) for _, name in sorted(model_names.items())
    ]
    thresholds = {
        "base_confidence": args.conf,
        "fire_threshold": args.conf,
        "smoke_threshold": args.conf,
        "imgsz": args.imgsz,
    }

    print(f"model_path: {model_path}")
    print(f"model_names: {model_names}")
    print(f"normalized_names: {normalized_names}")
    print(f"thresholds: {thresholds}")

    if args.image is None:
        print("raw_detections: []")
        print("kept_detections: []")
        print("sample_image: none")
        return 0

    image = _load_image(args.image)
    results = model.predict(image, imgsz=args.imgsz, conf=args.conf, verbose=False)
    raw_detections = _raw_detection_rows(results)
    kept_detections = [
        d
        for d in raw_detections
        if d["normalized_label"] in {"fire", "smoke"}
        and d["confidence"] >= thresholds[f"{d['normalized_label']}_threshold"]
    ]

    print(f"sample_image: {args.image}")
    print(f"raw_detections: {raw_detections}")
    print(f"kept_detections: {kept_detections}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
