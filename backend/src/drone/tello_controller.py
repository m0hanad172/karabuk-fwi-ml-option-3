from __future__ import annotations

import logging
import threading
import time

from configs import settings
from src.drone.models import DroneStatus

logger = logging.getLogger(__name__)


class TelloDroneController:
    """DJI Tello adapter prepared for operator-controlled demos.

    Importing djitellopy is delayed until connect(), so normal app startup and
    tests never require the hardware SDK.
    """

    mode = "tello"

    def __init__(self):
        self._tello = None
        self._frame_read = None
        self.connected = False
        self.stream_active = False
        self.battery: int | None = None
        self.last_error: str | None = None
        self.emergency_stopped = False
        self.hardware_available = True
        self._manual_override_until = 0.0

    def _import_tello(self):
        try:
            from djitellopy import Tello  # type: ignore
        except ImportError as e:
            self.hardware_available = False
            self.last_error = f"djitellopy not installed: {e}"
            return None
        return Tello

    def connect(self) -> DroneStatus:
        Tello = self._import_tello()
        if Tello is None:
            return self.get_status()
        try:
            if self._tello is None:
                Tello.RESPONSE_TIMEOUT = settings.DRONE_COMMAND_TIMEOUT_SECONDS
                self._tello = Tello(
                    host=settings.TELLO_IP,
                    retry_count=1,
                    vs_udp=settings.TELLO_VIDEO_PORT,
                )
            self._tello.connect()
            self.battery = int(self._tello.get_battery())
            self.connected = True
            self.emergency_stopped = False
            self.last_error = None
            logger.info("Tello connected; battery=%s%%", self.battery)
        except Exception as e:  # noqa: BLE001
            self.connected = False
            self.last_error = f"Tello connect failed: {e}"
            logger.warning(self.last_error)
        return self.get_status()

    def disconnect(self) -> DroneStatus:
        self.stop_stream()
        self.connected = False
        self._frame_read = None
        self._tello = None
        return self.get_status()

    def start_stream(self) -> DroneStatus:
        if not self.connected:
            self.connect()
        if not self.connected or self._tello is None:
            return self.get_status()
        
        if self.stream_active:
            return self.get_status()

        try:
            self._tello.streamon()
            time.sleep(1)
            self._frame_read = self._tello.get_frame_read()
            self.stream_active = True
            self.last_error = None
        except Exception as e:  # noqa: BLE001
            self.stream_active = False
            
            self.last_error = f"Tello stream failed: {e}"
            logger.warning(self.last_error)
        return self.get_status()

    def stop_stream(self) -> DroneStatus:
        if self._tello is not None and self.stream_active:
            try:
                self._tello.streamoff()
            except Exception as e:  # noqa: BLE001
                logger.warning("Tello streamoff failed: %s", e)
        self.stream_active = False
        self._frame_read = None
        return self.get_status()

    def get_status(self) -> DroneStatus:
        return DroneStatus(
            mode=self.mode,
            connected=self.connected,
            stream_active=self.stream_active,
            hardware_available=self.hardware_available,
            battery=self.battery,
            last_error=self.last_error,
            emergency_stopped=self.emergency_stopped,
            station_id=settings.DRONE_DEFAULT_STATION_ID,
        )

    def get_frame(self):
        if not self.stream_active or self._frame_read is None:
            return None
        frame = getattr(self._frame_read, "frame", None)
        if frame is None:
            return None
        try:
            import cv2
        except ImportError:
            return frame
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def manual_command(self, command: str) -> DroneStatus:
        if self._tello is None or not self.connected:
            self.last_error = "Tello is not connected"
            return self.get_status()

        speed = max(1, min(settings.DRONE_KEYBOARD_CONTROL_SPEED, 100))
        vectors = {
            "left": (-speed, 0, 0, 0),
            "right": (speed, 0, 0, 0),
            "forward": (0, speed, 0, 0),
            "back": (0, -speed, 0, 0),
            "stop": (0, 0, 0, 0),
        }
        vector = vectors.get(command)
        if vector is None:
            self.last_error = f"Manual command '{command}' is not supported"
            return self.get_status()

        try:
            pulse_seconds = max(settings.DRONE_KEYBOARD_PULSE_SECONDS, 0.0)
            self._manual_override_until = time.time() + pulse_seconds
            self._tello.send_rc_control(*vector)
            if command != "stop" and pulse_seconds > 0:
                time.sleep(pulse_seconds)
            self._send_zero_velocity(force=True)
            self.last_error = None
        except Exception as e:  # noqa: BLE001
            self.last_error = f"Tello manual command failed: {e}"
            logger.warning(self.last_error)
        return self.get_status()

    def demo_patrol(
        self,
        move_cm: int,
        up_cm: int,
        hover_seconds: float,
        delay_seconds: float,
        stop_event: threading.Event | None = None,
    ) -> list[str]:
        """Run the short controlled Tello demo patrol after service gates pass.

        Edit this function to change the controlled Tello demo patrol path.
        Tello movement values are centimeters. Keep distances conservative.
        """
        if self._tello is None or not self.connected:
            raise RuntimeError("Tello is not connected")

        executed: list[str] = []
        airborne = False
        landing_started = False
        try:
            if stop_event is not None and stop_event.is_set():
                executed.append("cancelled_before_takeoff")
                return executed

            self._tello.takeoff()
            airborne = True
            executed.append("takeoff")

            # Tello takeoff already rises to roughly the requested half-meter.
            # Avoid extra movement commands here; repeated zero RC commands
            # begin immediately after takeoff to avoid first-second drift.
            self._hold_position(delay_seconds, stop_event=stop_event)

            if up_cm > 0 and not self._stop_requested(stop_event):
                self._tello.move_up(up_cm)
                executed.append(f"move_up {up_cm}cm")
                self._hold_position(delay_seconds, stop_event=stop_event)

            # Keep holding position during the requested airborne window.
            executed.append(f"hover {hover_seconds:g}s")
            self._hold_position(hover_seconds, stop_event=stop_event)

            landing_started = True
            self._land_safely(executed)
            airborne = False
        except Exception as e:  # noqa: BLE001
            self.last_error = f"Tello demo patrol failed: {e}"
            logger.warning(self.last_error)
            if airborne and not landing_started:
                try:
                    self._land_safely(executed, label="land_after_error")
                except Exception as land_error:  # noqa: BLE001
                    logger.warning("Tello land after demo failure failed: %s", land_error)
            raise
        return executed

    def _send_zero_velocity(self, force: bool = False) -> None:
        if self._tello is None:
            return
        if not force and time.time() < self._manual_override_until:
            return
        try:
            self._tello.send_rc_control(0, 0, 0, 0)
        except Exception as e:  # noqa: BLE001
            logger.debug("Tello zero-velocity command skipped: %s", e)

    def _stop_requested(self, stop_event: threading.Event | None) -> bool:
        return bool(stop_event is not None and stop_event.is_set())

    def _hold_position(
        self,
        seconds: float,
        stop_event: threading.Event | None = None,
    ) -> None:
        end = time.time() + max(seconds, 0.0)
        self._send_zero_velocity(force=True)
        while time.time() < end:
            if self._stop_requested(stop_event):
                return
            time.sleep(min(0.1, max(end - time.time(), 0.0)))
            self._send_zero_velocity()

    def _land_safely(self, executed: list[str], label: str = "land") -> None:
        last_error: Exception | None = None
        self._send_zero_velocity(force=True)
        time.sleep(0.3)
        for attempt in range(2):
            try:
                self._tello.land()
                executed.append(label if attempt == 0 else f"{label}_retry")
                return
            except Exception as e:  # noqa: BLE001
                last_error = e
                logger.warning("Tello land attempt %s failed: %s", attempt + 1, e)
                time.sleep(0.8)
        raise RuntimeError(f"Tello landing failed: {last_error}")

    def emergency_stop(self) -> DroneStatus:
        if self._tello is not None and self.connected:
            try:
                self._tello.emergency()
            except Exception as e:  # noqa: BLE001
                self.last_error = f"Tello emergency stop failed: {e}"
                logger.warning(self.last_error)
        self.stream_active = False
        self.connected = False
        self.emergency_stopped = True
        return self.get_status()
