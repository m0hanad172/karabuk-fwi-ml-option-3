"""
Drone operational logic — separate layer, not part of the ML model.

Computes drone state based on the high-risk flag from the model decision.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from configs.settings import DRONE_INTERVAL_MINUTES
from src.api.time_utils import istanbul_now


def compute_drone_state(
    run_result: dict,
    allow_drone_trigger: bool,
    now: datetime | None = None,
) -> dict:
    # Always work in tz-aware Istanbul time so the computed next_launch
    # moment serialises with an explicit +03:00 offset.
    now = now or istanbul_now()
    active = bool(run_result.get("high_risk_flag")) and bool(allow_drone_trigger)
    next_launch = (now + timedelta(minutes=DRONE_INTERVAL_MINUTES)).isoformat() if active else None

    return {
        "active_alert_window": active,
        "drone_status": "ACTIVE_CYCLE" if active else "STANDBY",
        "drone_interval_minutes": DRONE_INTERVAL_MINUTES if active else None,
        "next_launch_time": next_launch,
        "reason": "High-risk flag active" if active else "No active flag or trigger disabled",
    }
