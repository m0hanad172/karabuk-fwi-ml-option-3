from __future__ import annotations

import logging
import time

from configs.settings import DRONE_DEFAULT_STATION_ID
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
                self._tello = Tello()
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
            station_id=DRONE_DEFAULT_STATION_ID,
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
        # Directional flight is intentionally not implemented here. Real
        # operator movement should remain with the drone controller app until
        # a full safety review defines command semantics.
        self.last_error = f"Manual command '{command}' is not implemented for Tello"
        return self.get_status()

    def demo_patrol(self, move_cm: int, up_cm: int, delay_seconds: float) -> list[str]:
        """Run the short controlled Tello demo patrol after service gates pass.

        Edit this function to change the controlled Tello demo patrol path.
        Tello movement values are centimeters. Keep distances conservative.
        """
        if self._tello is None or not self.connected:
            raise RuntimeError("Tello is not connected")

        route: list[tuple[str, tuple[int, ...]]] = [
            ("takeoff", ()),
            ("move_up", (up_cm,)),
            ("move_forward", (move_cm,)),
            ("move_right", (move_cm,)),
            ("move_back", (move_cm,)),
            ("move_left", (move_cm,)),
            ("land", ()),
        ]
        executed: list[str] = []
        try:
            for command, args in route:
                getattr(self._tello, command)(*args)
                executed.append(
                    command if not args else f"{command} {args[0]}cm"
                )
                time.sleep(delay_seconds)
        except Exception as e:  # noqa: BLE001
            self.last_error = f"Tello demo patrol failed: {e}"
            logger.warning(self.last_error)
            try:
                self._tello.land()
                executed.append("land_after_error")
            except Exception as land_error:  # noqa: BLE001
                logger.warning("Tello land after demo failure failed: %s", land_error)
            raise
        finally:
            self.stream_active = False
        return executed

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
