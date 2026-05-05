from __future__ import annotations

import time

from configs.settings import DRONE_DEFAULT_STATION_ID
from src.drone.models import DroneStatus


class MockDroneController:
    """No-hardware controller used by default for demos and tests."""

    mode = "mock"

    def __init__(self):
        self.connected = False
        self.stream_active = False
        self.battery = 100
        self.last_error: str | None = None
        self.emergency_stopped = False
        self.last_command: str | None = None
        self._tick = 0

    def connect(self) -> DroneStatus:
        self.connected = True
        self.emergency_stopped = False
        self.last_error = None
        return self.get_status()

    def disconnect(self) -> DroneStatus:
        self.stream_active = False
        self.connected = False
        return self.get_status()

    def start_stream(self) -> DroneStatus:
        if not self.connected:
            self.connect()
        self.stream_active = True
        self.last_error = None
        return self.get_status()

    def stop_stream(self) -> DroneStatus:
        self.stream_active = False
        return self.get_status()

    def get_status(self) -> DroneStatus:
        return DroneStatus(
            mode=self.mode,
            connected=self.connected,
            stream_active=self.stream_active,
            hardware_available=True,
            battery=self.battery,
            last_error=self.last_error,
            emergency_stopped=self.emergency_stopped,
            station_id=DRONE_DEFAULT_STATION_ID,
        )

    def get_frame(self):
        if not self.stream_active:
            return None
        try:
            import cv2
            import numpy as np
        except ImportError:
            return None

        self._tick += 1
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :] = (18, 35, 35)
        pulse = 40 + (self._tick % 80)
        cv2.circle(frame, (80 + pulse, 120), 18, (0, 110, 255), -1)
        cv2.putText(
            frame,
            "FireWatch Mock Drone Stream",
            (60, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (230, 245, 245),
            2,
        )
        cv2.putText(
            frame,
            time.strftime("%H:%M:%S"),
            (60, 280),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (170, 200, 200),
            1,
        )
        return frame

    def manual_command(self, command: str) -> DroneStatus:
        self.last_command = command
        return self.get_status()

    def demo_patrol(self, move_cm: int, up_cm: int, delay_seconds: float) -> list[str]:
        self.connected = True
        self.last_error = None
        route = [
            "takeoff",
            f"up {up_cm}",
            f"forward {move_cm}",
            f"right {move_cm}",
            f"back {move_cm}",
            f"left {move_cm}",
            "land",
        ]
        self.last_command = "demo_patrol"
        return route

    def emergency_stop(self) -> DroneStatus:
        self.stream_active = False
        self.connected = False
        self.emergency_stopped = True
        return self.get_status()
