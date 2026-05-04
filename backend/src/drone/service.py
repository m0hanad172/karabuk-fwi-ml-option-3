from __future__ import annotations

import logging
import threading
import time
from typing import Generator

from configs import settings
from src.drone.controller import DroneController
from src.drone.mock_controller import MockDroneController
from src.drone.models import DroneStatus
from src.monitoring import notifications as notif
from src.monitoring.cameras import INFERENCE_STRIDE, _CAPTURE_SLEEP
from src.monitoring.yolo_detector import run_detection

logger = logging.getLogger(__name__)


class DroneSafetyError(RuntimeError):
    """Raised when a drone command is blocked by safety configuration."""


class DroneService:
    """Operator-controlled drone-ready runtime service.

    This layer owns video streaming and optional fire/smoke detection on drone
    frames. It is deliberately separate from the risk prediction path; high risk
    may recommend patrol, but never calls this service directly.
    """

    def __init__(self):
        self.mode = settings.DRONE_MODE
        self.controller = self._build_controller(self.mode)
        self._lock = threading.Lock()
        self._stream_requested = False
        self._capture_thread: threading.Thread | None = None
        self._inference_thread: threading.Thread | None = None
        self._frame = None
        self._detections: list[dict] = []
        self._capture_fps = 0.0
        self._inference_fps = 0.0

    def _build_controller(self, mode: str) -> DroneController:
        if mode == "tello":
            from src.drone.tello_controller import TelloDroneController

            return TelloDroneController()
        return MockDroneController()

    def connect(self) -> dict:
        with self._lock:
            status = self.controller.connect()
        return self._decorate(status)

    def disconnect(self) -> dict:
        with self._lock:
            self._stream_requested = False
            status = self.controller.disconnect()
            self._frame = None
            self._detections = []
        return self._decorate(status)

    def start_stream(self) -> dict:
        if not settings.DRONE_VIDEO_ENABLED:
            raise DroneSafetyError("Drone video is disabled by configuration")
        with self._lock:
            self._stream_requested = True
            status = self.controller.start_stream()
            if status.stream_active:
                self._ensure_threads()
            else:
                self._stream_requested = False
        return self._decorate(status)

    def stop_stream(self) -> dict:
        with self._lock:
            self._stream_requested = False
            status = self.controller.stop_stream()
            self._frame = None
            self._detections = []
            self._capture_fps = 0.0
            self._inference_fps = 0.0
        return self._decorate(status)

    def get_status(self) -> dict:
        return self._decorate(self.controller.get_status())

    def manual_command(self, command: str, operator_confirmed: bool = False) -> dict:
        clean = command.strip().lower()
        if not settings.DRONE_ALLOW_MANUAL_CONTROL:
            raise DroneSafetyError("Manual drone control is disabled")
        if clean == "takeoff":
            if not settings.DRONE_ALLOW_AUTO_TAKEOFF:
                raise DroneSafetyError("Drone takeoff is disabled")
            if settings.DRONE_REQUIRE_OPERATOR_CONFIRMATION and not operator_confirmed:
                raise DroneSafetyError("Operator confirmation is required")
        status = self.controller.manual_command(clean)
        return self._decorate(status)

    def emergency_stop(self) -> dict:
        with self._lock:
            self._stream_requested = False
            status = self.controller.emergency_stop()
            self._frame = None
            self._detections = []
            self._capture_fps = 0.0
            self._inference_fps = 0.0
        return self._decorate(status)

    def patrol_state(self, risk_state: dict | None) -> dict:
        active = bool((risk_state or {}).get("active_alert_window"))
        return {
            "patrol_recommended": active,
            "physical_launch_allowed": False,
            "operator_confirmation_required": settings.DRONE_REQUIRE_OPERATOR_CONFIRMATION,
            "slot_minutes": settings.DRONE_PATROL_SLOT_MINUTES,
            "afternoon_cutoff_hour": settings.DRONE_AFTERNOON_CUTOFF_HOUR,
            "station_id": settings.DRONE_DEFAULT_STATION_ID,
            "message": (
                "High Risk prepares patrol; it does not auto-launch hardware."
                if active
                else "No active high-risk patrol recommendation."
            ),
        }

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        try:
            import cv2
        except ImportError:
            return

        boundary = b"--frame\r\n"
        while True:
            frame = self._frame
            if frame is None:
                time.sleep(0.2)
                continue

            draw = frame.copy()
            for det in self._detections:
                try:
                    x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
                    cv2.rectangle(draw, (x1, y1), (x2, y2), (0, 0, 255), 2)
                except Exception:  # noqa: BLE001
                    continue

            ok, buf = cv2.imencode(".jpg", draw, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                yield boundary + b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
            time.sleep(_CAPTURE_SLEEP)

    def _ensure_threads(self) -> None:
        if self._capture_thread is None or not self._capture_thread.is_alive():
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="drone-capture",
            )
            self._capture_thread.start()
        if self._inference_thread is None or not self._inference_thread.is_alive():
            self._inference_thread = threading.Thread(
                target=self._inference_loop,
                daemon=True,
                name="drone-inference",
            )
            self._inference_thread.start()

    def _capture_loop(self) -> None:
        last_sample = time.time()
        frames = 0
        while self._stream_requested:
            frame = self.controller.get_frame()
            if frame is not None:
                self._frame = frame
                frames += 1
            now = time.time()
            if now - last_sample >= 1.0:
                self._capture_fps = frames / max(now - last_sample, 0.001)
                frames = 0
                last_sample = now
            time.sleep(_CAPTURE_SLEEP)
        self._capture_fps = 0.0

    def _inference_loop(self) -> None:
        tick = 0
        last_sample = time.time()
        inferences = 0
        while self._stream_requested:
            frame = self._frame
            if frame is None:
                time.sleep(0.1)
                continue
            tick += 1
            if tick % INFERENCE_STRIDE != 0:
                time.sleep(_CAPTURE_SLEEP)
                continue
            detections = run_detection(frame)
            self._detections = detections
            inferences += 1
            if detections and notif.should_notify("drone"):
                image_url = notif.save_snapshot("drone", frame)
                notif.add_notification("drone", detections, image_url)
            now = time.time()
            if now - last_sample >= 1.0:
                self._inference_fps = inferences / max(now - last_sample, 0.001)
                inferences = 0
                last_sample = now
            time.sleep(_CAPTURE_SLEEP)
        self._inference_fps = 0.0

    def _decorate(self, status: DroneStatus) -> dict:
        status.detection_count = len(self._detections)
        status.capture_fps = self._capture_fps
        status.inference_fps = self._inference_fps
        status.manual_control_enabled = settings.DRONE_ALLOW_MANUAL_CONTROL
        status.auto_takeoff_enabled = settings.DRONE_ALLOW_AUTO_TAKEOFF
        status.operator_confirmation_required = (
            settings.DRONE_REQUIRE_OPERATOR_CONFIRMATION
        )
        status.station_id = settings.DRONE_DEFAULT_STATION_ID
        out = status.to_dict()
        out["inference_stride"] = INFERENCE_STRIDE
        return out


_service: DroneService | None = None
_service_lock = threading.Lock()


def get_drone_service() -> DroneService:
    global _service
    with _service_lock:
        if _service is None:
            _service = DroneService()
        return _service


def reset_drone_service_for_tests() -> None:
    global _service
    with _service_lock:
        if _service is not None:
            try:
                _service.stop_stream()
            except Exception:  # noqa: BLE001
                pass
        _service = None
