"""
Live weather display source — display-only, NOT for model input.

Fetches current weather snapshot for dashboard weather cards.
Strictly separated from the model input pipeline.
"""
from __future__ import annotations

import requests

from configs.settings import LATITUDE, LONGITUDE, TIMEZONE, DISPLAY_TIMEZONE
from src.api.time_utils import istanbul_now_iso

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

CURRENT_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
    "cloud_cover",
]


def fetch_live_weather_snapshot(
    latitude: float = LATITUDE,
    longitude: float = LONGITUDE,
    timezone: str = TIMEZONE,
) -> dict:
    """
    Fetch current weather for display cards.

    Returns a dict with current readings + metadata timestamps.
    This data must NEVER be used as model input.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "current": ",".join(CURRENT_VARS),
    }
    # Live display is polled from the browser — fail fast rather than
    # blocking the UI for half a minute on a stalled upstream.
    response = requests.get(FORECAST_URL, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    current = payload.get("current", {})

    return {
        "source": "open_meteo_current",
        "source_time": current.get("time"),
        "fetch_time": istanbul_now_iso(),
        "display_timezone": DISPLAY_TIMEZONE,
        "temperature_now": current.get("temperature_2m"),
        "rh_now": current.get("relative_humidity_2m"),
        "ws_now": current.get("wind_speed_10m"),
        "precip_now": current.get("precipitation"),
        "cloud_cover_now": current.get("cloud_cover"),
        "is_display_only": True,
    }
