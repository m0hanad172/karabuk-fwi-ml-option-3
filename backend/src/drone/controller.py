from __future__ import annotations

from typing import Any, Protocol

from src.drone.models import DroneStatus


class DroneController(Protocol):
    """Minimal hardware adapter contract.

    Implementations must treat stream start as video-only. Physical takeoff is
    never implied by this interface.
    """

    mode: str

    def connect(self) -> DroneStatus:
        ...

    def disconnect(self) -> DroneStatus:
        ...

    def start_stream(self) -> DroneStatus:
        ...

    def stop_stream(self) -> DroneStatus:
        ...

    def get_status(self) -> DroneStatus:
        ...

    def get_frame(self) -> Any | None:
        ...

    def manual_command(self, command: str) -> DroneStatus:
        ...

    def emergency_stop(self) -> DroneStatus:
        ...
