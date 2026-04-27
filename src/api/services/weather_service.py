"""Service layer for live weather display."""
from __future__ import annotations

from src.data.live_display import fetch_live_weather_snapshot
from src.api.db.database import set_system_state


def get_live_weather() -> dict:
    """Fetch live weather snapshot (display-only) and cache it."""
    snapshot = fetch_live_weather_snapshot()
    set_system_state("latest_live_weather", snapshot)
    return snapshot
