from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class DroneStatus:
    mode: str
    connected: bool = False
    stream_active: bool = False
    hardware_available: bool = True
    battery: int | None = None
    last_error: str | None = None
    detection_count: int = 0
    capture_fps: float = 0.0
    inference_fps: float = 0.0
    manual_control_enabled: bool = False
    auto_takeoff_enabled: bool = False
    operator_confirmation_required: bool = True
    emergency_stopped: bool = False
    station_id: str = "station_1"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "connected": self.connected,
            "stream_active": self.stream_active,
            "running": self.stream_active,
            "hardware_available": self.hardware_available,
            "battery": self.battery,
            "last_error": self.last_error,
            "detection_count": self.detection_count,
            "capture_fps": round(self.capture_fps, 1),
            "inference_fps": round(self.inference_fps, 1),
            "manual_control_enabled": self.manual_control_enabled,
            "auto_takeoff_enabled": self.auto_takeoff_enabled,
            "operator_confirmation_required": self.operator_confirmation_required,
            "emergency_stopped": self.emergency_stopped,
            "station_id": self.station_id,
        }


class ManualDroneCommand(BaseModel):
    command: str = Field(..., min_length=1, max_length=40)
    operator_confirmed: bool = False
