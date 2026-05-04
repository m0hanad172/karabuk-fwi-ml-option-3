"""Compatibility facade for the drone video feed endpoints.

The hardware-facing implementation lives in ``src.drone``. This module keeps
the existing ``/monitoring/drone/*`` routes working without preserving the old
global Tello state style.
"""
from __future__ import annotations

from typing import Generator

from src.drone.service import get_drone_service


def start_drone() -> dict:
    """Start the operator-controlled drone/video stream.

    This never implies physical takeoff.
    """
    return get_drone_service().start_stream()


def stop_drone() -> dict:
    return get_drone_service().stop_stream()


def get_drone_status() -> dict:
    return get_drone_service().get_status()


def mjpeg_generator() -> Generator[bytes, None, None]:
    yield from get_drone_service().mjpeg_generator()
