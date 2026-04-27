"""DJI Tello drone feed + YOLO fire detection.

Cleaned migration of ``legacy_detection_reference/drone.py``.

Phase 5 redesign: the drone feed now uses the same split
capture/inference design as ``cameras.py`` — one thread pumps Tello
frames into ``_state.frame``, a second thread runs YOLO every Nth frame.
This keeps the MJPEG feed smooth even when YOLO CPU inference is slow,
and lets the drone stream yield its first frame instantly when Start is
pressed (YOLO is prewarmed at app startup in ``api/main.py``).

Important differences from the legacy prototype:
  - ``djitellopy`` is an *optional* dependency. If hardware or the library
    is unavailable the drone endpoints return a "hardware unavailable"
    status instead of crashing, and the feed generator yields nothing.
  - Auto takeoff/land is removed — it must stay operator-driven.
  - This module has no link to the Option 3 prediction pipeline or the
    `/drone/state` operational policy layer (``src/pipeline/drone_logic.py``).
    They are different concerns on purpose: ``/drone/state`` decides
    *when* the drone should fly based on predicted FWI risk; this module
    streams whatever video the drone is producing, independently.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Generator

from src.monitoring import notifications as notif
from src.monitoring.cameras import INFERENCE_STRIDE, _CAPTURE_SLEEP
from src.monitoring.yolo_detector import run_detection

logger = logging.getLogger(__name__)


@dataclass
class DroneState:
    running: bool = False
    connected: bool = False
    last_error: str | None = None
    battery: int | None = None
    frame: object | None = None  # numpy ndarray, BGR — latest raw frame
    detections: list[dict] = field(default_factory=list)
    capture_thread: threading.Thread | None = None
    inference_thread: threading.Thread | None = None
    capture_fps: float = 0.0
    inference_fps: float = 0.0


_state = DroneState()
_state_lock = threading.Lock()


def _try_import_tello():
    try:
        from djitellopy import Tello  # type: ignore
        return Tello
    except ImportError as e:
        logger.warning("djitellopy not installed: %s", e)
        return None


def _drone_capture_loop() -> None:
    """Pure capture — resize + colour-convert + store into ``_state.frame``.
    No YOLO here so inference never starves the frame pump."""
    try:
        import cv2
    except ImportError as e:
        _state.last_error = f"opencv not installed: {e}"
        _state.running = False
        logger.error(_state.last_error)
        return

    Tello = _try_import_tello()
    if Tello is None:
        _state.last_error = "djitellopy not installed (drone hardware library missing)"
        _state.running = False
        return

    try:
        tello = Tello()
        tello.connect()
        _state.battery = int(tello.get_battery())
        _state.connected = True
        logger.info("Drone connected; battery=%s%%", _state.battery)
    except Exception as e:  # noqa: BLE001 — hardware errors are expected
        _state.last_error = f"drone connect failed: {e}"
        _state.running = False
        _state.connected = False
        logger.warning(_state.last_error)
        return

    try:
        tello.streamon()
        time.sleep(2)
        cap = tello.get_frame_read()
    except Exception as e:  # noqa: BLE001
        _state.last_error = f"drone stream failed: {e}"
        _state.running = False
        _state.connected = False
        logger.warning(_state.last_error)
        return

    last_fps_sample = time.time()
    frames_since_sample = 0

    try:
        while _state.running:
            img = cap.frame
            if img is None:
                time.sleep(0.05)
                continue

            img = cv2.resize(img, (640, 480))
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            _state.frame = img_bgr

            frames_since_sample += 1
            now = time.time()
            if now - last_fps_sample >= 1.0:
                _state.capture_fps = frames_since_sample / (now - last_fps_sample)
                frames_since_sample = 0
                last_fps_sample = now

            time.sleep(_CAPTURE_SLEEP)
    finally:
        try:
            tello.streamoff()
        except Exception as e:  # noqa: BLE001
            logger.warning("drone streamoff failed: %s", e)
        _state.connected = False
        _state.capture_fps = 0.0
        logger.info("Drone capture loop stopped")


def _drone_inference_loop() -> None:
    """Run YOLO on the latest drone frame every Nth iteration."""
    try:
        import cv2
    except ImportError:
        return

    tick = 0
    last_fps_sample = time.time()
    inferences_since_sample = 0

    try:
        while _state.running:
            frame = _state.frame
            if frame is None:
                time.sleep(0.1)
                continue

            tick += 1
            if tick % INFERENCE_STRIDE != 0:
                time.sleep(_CAPTURE_SLEEP)
                continue

            detections = run_detection(frame)
            _state.detections = detections
            inferences_since_sample += 1

            if detections and notif.should_notify("drone"):
                annotated = frame.copy()
                for det in detections:
                    x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(
                        annotated,
                        f"Fire {det['confidence']:.2f}",
                        (x1, max(0, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2,
                    )
                image_url = notif.save_snapshot("drone", annotated)
                notif.add_notification("drone", detections, image_url)

            now = time.time()
            if now - last_fps_sample >= 1.0:
                _state.inference_fps = inferences_since_sample / (now - last_fps_sample)
                inferences_since_sample = 0
                last_fps_sample = now

            time.sleep(_CAPTURE_SLEEP)
    finally:
        _state.inference_fps = 0.0
        logger.info("Drone inference loop stopped")


def start_drone() -> dict:
    """Start the drone capture + inference loops. Returns current status dict."""
    with _state_lock:
        if _state.running:
            return get_drone_status()
        _state.running = True
        _state.last_error = None
        _state.capture_thread = threading.Thread(
            target=_drone_capture_loop, daemon=True, name="cap-drone"
        )
        _state.inference_thread = threading.Thread(
            target=_drone_inference_loop, daemon=True, name="inf-drone"
        )
        _state.capture_thread.start()
        _state.inference_thread.start()
    return get_drone_status()


def stop_drone() -> dict:
    with _state_lock:
        _state.running = False
    return get_drone_status()


def get_drone_status() -> dict:
    return {
        "running": _state.running,
        "connected": _state.connected,
        "battery": _state.battery,
        "last_error": _state.last_error,
        "detection_count": len(_state.detections),
        "hardware_available": _try_import_tello() is not None,
        "capture_fps": round(_state.capture_fps, 1),
        "inference_fps": round(_state.inference_fps, 1),
        "inference_stride": INFERENCE_STRIDE,
    }


def mjpeg_generator() -> Generator[bytes, None, None]:
    """MJPEG byte stream for the drone feed. Same low-latency pattern as
    the camera MJPEG generator — just reads the latest annotated frame."""
    try:
        import cv2
    except ImportError:
        return

    boundary = b"--frame\r\n"
    first_frame_deadline = time.time() + 2.0
    last_emit = 0.0

    while True:
        if not _state.running or _state.frame is None:
            if time.time() < first_frame_deadline and _state.running:
                time.sleep(0.02)
                continue
            time.sleep(0.2)
            first_frame_deadline = time.time() + 2.0
            continue

        now = time.time()
        if now - last_emit < _CAPTURE_SLEEP:
            time.sleep(max(0.0, _CAPTURE_SLEEP - (now - last_emit)))
        last_emit = time.time()

        draw = _state.frame.copy()
        for det in _state.detections:
            try:
                x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
                cv2.rectangle(draw, (x1, y1), (x2, y2), (0, 0, 255), 2)
            except Exception:  # noqa: BLE001
                continue

        ok, buf = cv2.imencode(".jpg", draw, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            time.sleep(0.02)
            continue
        yield boundary + b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
