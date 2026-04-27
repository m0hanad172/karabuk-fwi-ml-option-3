"""Drone state endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from src.api.db.database import get_system_state

router = APIRouter(prefix="/drone", tags=["drone"])


@router.get("/state", summary="Get current drone state")
async def drone_state():
    """Get the latest drone state from the most recent risk check."""
    state = get_system_state("latest_drone_state")
    if state is None:
        return {
            "active_alert_window": False,
            "drone_status": "NO_DATA",
            "drone_interval_minutes": None,
            "next_launch_time": None,
            "reason": "No risk check has been run yet",
        }
    return state
