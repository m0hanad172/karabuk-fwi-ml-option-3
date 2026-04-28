"""Camera capture + YOLO fire detection.

Cleaned migration of ``legacy_detection_reference/cameras.py``.

Exposes two logical cameras:
  - ``pc_camera`` (default index 0 — built-in laptop camera)
  - ``webcam``    (default index 1 — USB webcam)

Phase 5 perf redesign
---------------------
Previously every camera thread did ``read → YOLO → store → sleep`` in a
single loop. YOLO CPU inference dominated the loop (80–150 ms/frame),
which both starved the frame buffer (stuttery feeds) and made "Start"
feel broken because the first frame had to pay for the cold YOLO load.

The new design:

1. **Capture thread** pulls frames from ``cv2.VideoCapture`` at full
   device FPS and writes them to ``state.frame``. This loop is pure I/O —
   no detection, no encoding.
2. **Inference thread** reads the latest frame every Nth iteration (stride
   is env-tunable, default 3 → ~6 FPS inference from ~20 FPS capture) and
   updates ``state.detections``. YOLO cold-load is also prewarmed at app
   startup in ``api/main.py`` so "first frame" feels instant.
3. The MJPEG generator reads the latest annotated frame without ever
   blocking on inference.

Errors are also now structured: ``state.last_error`` is a dict
``{code, message}`` so the frontend can render precise copy ("device
index 1 not present" vs "opencv missing") instead of a raw string.

Env knobs (all optional, sane defaults):
  - ``MONITORING_YOLO_IMGSZ``     — YOLO input size (default 640)
  - ``MONITORING_YOLO_CONF``      — confidence threshold (default 0.4)
  - ``MONITORING_INFERENCE_STRIDE`` — run YOLO every Nth capture (default 3)
  - ``MONITORING_CAPTURE_FPS_CAP`` — capture loop sleep target (default 25)

Monitoring stays strictly separated from the Option 3 prediction path.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Generator

from src.monitoring import camera_mapping
from src.monitoring import notifications as notif
from src.monitoring.yolo_detector import run_detection

logger = logging.getLogger(__name__)


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


INFERENCE_STRIDE = max(1, _env_int("MONITORING_INFERENCE_STRIDE", 3))
CAPTURE_FPS_CAP = max(5, _env_int("MONITORING_CAPTURE_FPS_CAP", 25))
_CAPTURE_SLEEP = 1.0 / CAPTURE_FPS_CAP


@dataclass
class CameraError:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass
class CameraState:
    cam_id: str
    index: int
    running: bool = False
    frame: object | None = None  # numpy ndarray, BGR — latest raw frame
    detections: list[dict] = field(default_factory=list)
    last_error: CameraError | None = None
    capture_thread: threading.Thread | None = None
    inference_thread: threading.Thread | None = None
    # Diagnostics exposed on /status so the Monitoring tab can render
    # a small perf chip per feed.
    capture_fps: float = 0.0
    inference_fps: float = 0.0
    frames_captured: int = 0
    frames_inferred: int = 0


# Camera registry — fixed logical IDs, runtime-remappable device indices.
#
# Physical intent (Karabük project hardware):
#   pc_camera → Built-in laptop camera (usually 720p)
#   webcam    → Logitech BRIO 100 (USB, 1080p capable) — the dedicated
#               project webcam.
#
# Default indices below match the *most common Windows enumeration order*
# (built-in at 0, first external USB at 1). On machines where DSHOW
# enumerates differently the operator has two ways to fix it:
#   1. Click "Auto-detect" on the Devices strip → backend probes every
#      index, picks the highest-resolution opened device as the BRIO, and
#      remaps the indices in place.
#   2. Click "Assign to Webcam" / "Assign to PC Camera" on any row of the
#      strip to force a specific index for a specific logical camera.
# Both paths call POST /monitoring/cameras/{cam_id}/remap — no restart.
CAMERAS: dict[str, CameraState] = {
    "pc_camera": CameraState(cam_id="pc_camera", index=0),
    "webcam": CameraState(cam_id="webcam", index=1),
}

# Apply the persisted mapping immediately. No-op on first run (no file
# yet). This is the one side effect this module has at import time —
# matching the existing `CAMERAS` initialisation pattern rather than
# adding a separate startup call.
try:
    camera_mapping.apply_mapping(CAMERAS)
except Exception as _e:  # noqa: BLE001 — never let a corrupt mapping
                         # file break the backend boot
    logger.warning("Could not apply persisted camera mapping: %s", _e)


# BRIO 100 claims 1920×1080 natively. Anything ≥ 1920 wide on the DSHOW
# probe is treated as "probably the BRIO"; anything below that is treated
# as the built-in. Used by ``auto_detect_cameras``.
_BRIO_MIN_WIDTH = 1920
CAMERA_UNAVAILABLE_MESSAGE = (
    "Camera is unavailable in this runtime. For webcam monitoring, "
    "run the backend locally or configure Docker device passthrough."
)


def _camera_unavailable_error(index: int) -> CameraError:
    return CameraError(
        code="device_not_found",
        message=f"{CAMERA_UNAVAILABLE_MESSAGE} OpenCV index: {index}.",
    )


def _open_capture(index: int):
    """Open a camera with the best backend for the current runtime."""
    try:
        import cv2
    except ImportError as e:
        return None, CameraError(
            code="opencv_missing", message=f"opencv not installed: {e}"
        )

    if os.name == "nt":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)
    else:
        cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        return None, _camera_unavailable_error(index)
    return cap, None


# ---------------------------------------------------------------------------
# Capture + inference loops
# ---------------------------------------------------------------------------


def _capture_loop(cam_id: str) -> None:
    """Pure capture — reads frames into ``state.frame`` as fast as the
    device allows (capped by CAPTURE_FPS_CAP). Never calls YOLO."""
    try:
        import cv2
    except ImportError as e:
        CAMERAS[cam_id].last_error = CameraError(
            code="opencv_missing", message=f"opencv not installed: {e}"
        )
        CAMERAS[cam_id].running = False
        logger.error(CAMERAS[cam_id].last_error.message)
        return

    state = CAMERAS[cam_id]

    cap, open_error = _open_capture(state.index)
    if cap is None:
        state.last_error = open_error or _camera_unavailable_error(state.index)
        state.running = False
        logger.warning("Camera %s (%s): %s", cam_id, state.index, state.last_error.message)
        return

    logger.info("Camera %s started on index %s", cam_id, state.index)
    state.last_error = None

    last_fps_sample = time.time()
    frames_since_sample = 0

    try:
        while state.running:
            ok, frame = cap.read()
            if not ok or frame is None:
                # A transient read failure isn't fatal — just retry
                # slowly. A persistent failure will show up on the
                # status card via zero capture_fps.
                time.sleep(0.05)
                continue

            state.frame = frame
            state.frames_captured += 1
            frames_since_sample += 1

            # Sample capture FPS every second.
            now = time.time()
            if now - last_fps_sample >= 1.0:
                state.capture_fps = frames_since_sample / (now - last_fps_sample)
                frames_since_sample = 0
                last_fps_sample = now

            time.sleep(_CAPTURE_SLEEP)
    finally:
        cap.release()
        state.capture_fps = 0.0
        state.frame = None
        state.detections = []
        logger.info("Camera %s capture loop stopped", cam_id)


def _inference_loop(cam_id: str) -> None:
    """Runs YOLO on the latest frame every Nth iteration and writes
    detections + notifications. Separate from the capture loop so slow
    inference cannot stall frame delivery."""
    try:
        import cv2  # noqa: F401 — imported so we fail early if missing
    except ImportError:
        return

    state = CAMERAS[cam_id]
    tick = 0
    last_fps_sample = time.time()
    inferences_since_sample = 0

    try:
        while state.running:
            frame = state.frame
            if frame is None:
                time.sleep(0.1)
                continue

            tick += 1
            if tick % INFERENCE_STRIDE != 0:
                time.sleep(_CAPTURE_SLEEP)
                continue

            detections = run_detection(frame)
            state.detections = detections
            state.frames_inferred += 1
            inferences_since_sample += 1

            if detections and notif.should_notify(cam_id):
                try:
                    import cv2
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
                    image_url = notif.save_snapshot(cam_id, annotated)
                    notif.add_notification(cam_id, detections, image_url)
                except Exception as e:  # noqa: BLE001
                    logger.warning("snapshot save failed for %s: %s", cam_id, e)

            now = time.time()
            if now - last_fps_sample >= 1.0:
                state.inference_fps = inferences_since_sample / (now - last_fps_sample)
                inferences_since_sample = 0
                last_fps_sample = now

            time.sleep(_CAPTURE_SLEEP)
    finally:
        state.inference_fps = 0.0
        logger.info("Camera %s inference loop stopped", cam_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_camera(cam_id: str) -> bool:
    """Start capture + inference threads for a camera. Returns True on success."""
    if cam_id not in CAMERAS:
        return False
    state = CAMERAS[cam_id]
    if state.running:
        return True

    # Preflight the device before telling the frontend the feed is live.
    # Without this, Docker/no-permission/no-device cases briefly report
    # running=True while the capture thread fails in the background, which
    # leaves the Monitoring tab showing a dead MJPEG image until the next
    # status poll.
    cap, open_error = _open_capture(state.index)
    if cap is None:
        state.running = False
        state.last_error = open_error or _camera_unavailable_error(state.index)
        state.frame = None
        state.detections = []
        state.capture_fps = 0.0
        state.inference_fps = 0.0
        return False
    cap.release()

    state.running = True
    state.last_error = None
    state.frames_captured = 0
    state.frames_inferred = 0
    state.capture_thread = threading.Thread(
        target=_capture_loop, args=(cam_id,), daemon=True, name=f"cap-{cam_id}"
    )
    state.inference_thread = threading.Thread(
        target=_inference_loop, args=(cam_id,), daemon=True, name=f"inf-{cam_id}"
    )
    state.capture_thread.start()
    state.inference_thread.start()
    return True


def stop_camera(cam_id: str) -> bool:
    if cam_id not in CAMERAS:
        return False
    state = CAMERAS[cam_id]
    state.running = False
    # Clear the last frame + detections so the UI doesn't keep showing a
    # stale snapshot after Stop. Without this, the MJPEG <img> sometimes
    # held the final captured frame until the next Start, which looked
    # like the feed was "frozen on a static image" rather than stopped.
    state.frame = None
    state.detections = []
    state.capture_fps = 0.0
    state.inference_fps = 0.0
    return True


def remap_camera(cam_id: str, new_index: int) -> bool:
    """Change a camera's device index. Stops the camera if running — the
    caller must explicitly restart it. Returns True if the camera exists.

    If ``new_index`` is currently assigned to the *other* logical camera
    we swap them, so the operator can fix a wrong mapping in one click
    without manually moving both cameras to unused indices first.
    """
    if cam_id not in CAMERAS:
        return False
    new_index = int(new_index)
    state = CAMERAS[cam_id]

    # Detect swap: another camera already holds this index.
    other_id = next(
        (cid for cid, st in CAMERAS.items() if cid != cam_id and st.index == new_index),
        None,
    )

    if state.running:
        stop_camera(cam_id)
    if other_id is not None and CAMERAS[other_id].running:
        stop_camera(other_id)
    # Give capture threads a moment to release their devices.
    time.sleep(0.3)

    old_index = state.index
    state.index = new_index
    state.last_error = None
    state.frame = None
    state.detections = []

    if other_id is not None:
        # Swap: the other camera gets this camera's old index.
        CAMERAS[other_id].index = old_index
        CAMERAS[other_id].last_error = None
        CAMERAS[other_id].frame = None
        CAMERAS[other_id].detections = []
        logger.info(
            "Swapped camera indices: %s=%s, %s=%s",
            cam_id, new_index, other_id, old_index,
        )
    else:
        logger.info("Remapped %s to index %s", cam_id, new_index)

    # Re-probe so we can stamp a fresh fingerprint on the mapping file.
    # discover_devices is read-only and safe to call here; the heavy
    # YOLO inference threads are already stopped above.
    try:
        fresh = discover_devices()
        camera_mapping.apply_discovered_fingerprint(CAMERAS, fresh)
        camera_mapping.save_mapping(CAMERAS)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not persist camera mapping after remap: %s", e)
    return True


def auto_detect_cameras(max_index: int = 4) -> dict:
    """Probe every local index and assign the highest-resolution one to
    ``webcam`` (the Logitech BRIO 100 reports 1920×1080 on DSHOW) and the
    next one to ``pc_camera``.

    Returns a dict describing what was reassigned so the frontend can show
    the operator what changed. Safe to call at any time: cameras that are
    running are stopped first, the registry is updated, and the operator
    can press Start again.
    """
    devices = discover_devices(max_index=max_index)
    opened = [d for d in devices if d["opened"]]
    if not opened:
        return {"changed": False, "reason": "no_devices_opened", "devices": devices}

    # Highest-resolution opened index → webcam (BRIO). If there is a clear
    # 1080p-class device we prefer it; otherwise we just take the max.
    ranked = sorted(opened, key=lambda d: (d["width"], d["height"]), reverse=True)
    brio_candidate = next(
        (d for d in ranked if d["width"] >= _BRIO_MIN_WIDTH), ranked[0]
    )

    # Single-device case: no safe way to split webcam vs pc_camera onto
    # distinct indices. Assign whichever slot is unassigned (prefer
    # pc_camera — the built-in is the more common "only one camera"
    # situation) and leave the other alone with a "need second device"
    # reason so the UI can tell the operator to plug in the BRIO.
    if len(opened) == 1:
        only_index = int(opened[0]["index"])
        is_brio_class = opened[0]["width"] >= _BRIO_MIN_WIDTH
        target_cam = "webcam" if is_brio_class else "pc_camera"
        prev_index = CAMERAS[target_cam].index
        if prev_index != only_index:
            if CAMERAS[target_cam].running:
                stop_camera(target_cam)
                time.sleep(0.3)
            CAMERAS[target_cam].index = only_index
            CAMERAS[target_cam].last_error = None
            CAMERAS[target_cam].frame = None
            CAMERAS[target_cam].detections = []
        try:
            camera_mapping.apply_discovered_fingerprint(CAMERAS, devices)
            camera_mapping.save_mapping(CAMERAS)
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not persist camera mapping: %s", e)
        return {
            "changed": prev_index != only_index,
            "reason": "single_device_only",
            "assignments": {cid: st.index for cid, st in CAMERAS.items()},
            "brio_detected": is_brio_class,
            "devices": devices,
        }

    webcam_index = int(brio_candidate["index"])

    # pc_camera gets the next opened index that isn't the BRIO.
    remaining = [d for d in opened if int(d["index"]) != webcam_index]
    pc_index = int(remaining[0]["index"]) if remaining else CAMERAS["pc_camera"].index

    prev = {cid: st.index for cid, st in CAMERAS.items()}

    # Stop both before remap so device handles release cleanly.
    for cid in CAMERAS:
        if CAMERAS[cid].running:
            stop_camera(cid)
    time.sleep(0.3)

    CAMERAS["webcam"].index = webcam_index
    CAMERAS["webcam"].last_error = None
    CAMERAS["webcam"].frame = None
    CAMERAS["webcam"].detections = []

    CAMERAS["pc_camera"].index = pc_index
    CAMERAS["pc_camera"].last_error = None
    CAMERAS["pc_camera"].frame = None
    CAMERAS["pc_camera"].detections = []

    changed = (
        prev["webcam"] != webcam_index or prev["pc_camera"] != pc_index
    )
    logger.info(
        "auto_detect_cameras: webcam %s→%s, pc_camera %s→%s (changed=%s)",
        prev["webcam"], webcam_index, prev["pc_camera"], pc_index, changed,
    )
    # Stamp fingerprints from the probe we just ran + persist.
    try:
        camera_mapping.apply_discovered_fingerprint(CAMERAS, devices)
        camera_mapping.save_mapping(CAMERAS)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not persist camera mapping: %s", e)
    return {
        "changed": changed,
        "previous": prev,
        "assignments": {
            "webcam": webcam_index,
            "pc_camera": pc_index,
        },
        "brio_detected": brio_candidate["width"] >= _BRIO_MIN_WIDTH,
        "devices": devices,
    }


def get_camera_status(cam_id: str) -> dict:
    if cam_id not in CAMERAS:
        return {"cam_id": cam_id, "exists": False}
    state = CAMERAS[cam_id]
    return {
        "cam_id": cam_id,
        "exists": True,
        "running": state.running,
        "index": state.index,
        "detection_count": len(state.detections),
        "last_error": state.last_error.to_dict() if state.last_error else None,
        "capture_fps": round(state.capture_fps, 1),
        "inference_fps": round(state.inference_fps, 1),
        "frames_captured": state.frames_captured,
        "frames_inferred": state.frames_inferred,
        "inference_stride": INFERENCE_STRIDE,
    }


def list_cameras() -> list[dict]:
    return [get_camera_status(cid) for cid in CAMERAS]


def discover_devices(max_index: int = 4) -> list[dict]:
    """Probe local camera indices and report which ones actually open.

    Called by the frontend Devices Detected strip. Does *not* leave any
    device held open — each probe is immediately released. Safe to call
    while other cameras are already running (a device that's already in
    use will probe as ``opened=False`` on Windows, which is the expected
    and useful signal).
    """
    out: list[dict] = []
    try:
        import cv2
    except ImportError:
        return out

    for idx in range(max_index):
        if os.name == "nt":
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(idx)
        else:
            cap = cv2.VideoCapture(idx)
        opened = cap.isOpened()
        if opened:
            # Attempt 1080p to measure the device's true max resolution —
            # helps the operator identify devices (Logitech BRIO → 1080p,
            # built-in laptop camera → usually 720p).
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
        else:
            width = height = 0
            fps = 0.0
        cap.release()

        assigned_to = None
        for cam_id, st in CAMERAS.items():
            if st.index == idx:
                assigned_to = cam_id
                break

        out.append(
            {
                "index": idx,
                "opened": opened,
                "width": width,
                "height": height,
                "fps": round(fps, 1),
                "assigned_to": assigned_to,
            }
        )
    return out


# ---------------------------------------------------------------------------
# MJPEG generator
# ---------------------------------------------------------------------------


def mjpeg_generator(cam_id: str) -> Generator[bytes, None, None]:
    """MJPEG byte stream for a camera. Yields frames at capture rate,
    draws the latest detections (read-only — never calls YOLO).

    On start we wait at most ~1 s for the first frame to arrive, then
    yield immediately. This replaces the old 200 ms poll loop that gave
    the UI a visible delay after clicking Start.
    """
    try:
        import cv2
    except ImportError:
        return

    boundary = b"--frame\r\n"
    first_frame_deadline = time.time() + 2.0
    last_emit = 0.0

    while True:
        state = CAMERAS.get(cam_id)
        if state is None:
            time.sleep(0.2)
            continue
        frame = state.frame
        if frame is None or not state.running:
            if time.time() < first_frame_deadline and state.running:
                time.sleep(0.02)
                continue
            # Idle quietly until Start flips the flag.
            time.sleep(0.2)
            first_frame_deadline = time.time() + 2.0
            continue

        # Throttle emit rate to capture cap — no point encoding more
        # frames than the device produces.
        now = time.time()
        if now - last_emit < _CAPTURE_SLEEP:
            time.sleep(max(0.0, _CAPTURE_SLEEP - (now - last_emit)))
        last_emit = time.time()

        draw = frame.copy()
        for det in state.detections:
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
