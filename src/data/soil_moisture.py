"""
Soil moisture resolver with daily + hourly fallback.
Adapted from old project — logic validated.

Phase 5 perf work:
  - Added ``fetch_daily_soil_moisture_range`` — one Open-Meteo call returning
    ``{date_str: value}`` for an entire range. This replaces the per-day loop
    in ``fetch_weather.py`` which used to fire 40+ sequential HTTP calls
    against Open-Meteo for a single history window.
  - Tightened per-call timeouts from 60s → 15s. 60s is unreasonable for an
    interactive manual-check path; a stalled weather call should surface
    as a fast error instead of hanging the UI for a minute.
  - Added a tiny in-memory LRU cache so single-day resolves inside one
    risk check aren't repeated by both the feature build and the model-input
    fetch.
"""
from __future__ import annotations

from functools import lru_cache

import requests
import pandas as pd

from configs.settings import LATITUDE, LONGITUDE, TIMEZONE
from src.api.time_utils import istanbul_today

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_VAR = "soil_moisture_0_to_7cm_mean"
HOURLY_LAYERS = [
    "soil_moisture_0_to_1cm",
    "soil_moisture_1_to_3cm",
    "soil_moisture_3_to_9cm",
]

# Interactive paths (manual risk check) must fail fast, not hang for a
# minute. The scheduled path is tolerant of a re-run on failure.
_HTTP_TIMEOUT = 15


def _request_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=_HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _pick_source(target_date: str) -> str:
    today = istanbul_today()
    return FORECAST_URL if pd.to_datetime(target_date).date() >= today else ARCHIVE_URL


def fetch_daily_soil_moisture_range(
    start_date: str,
    end_date: str,
    latitude: float = LATITUDE,
    longitude: float = LONGITUDE,
    timezone: str = TIMEZONE,
) -> dict[str, float | None]:
    """Fetch the daily 0–7 cm soil moisture mean across ``[start_date, end_date]``
    in a **single** Open-Meteo call.

    Returns a ``{yyyy-mm-dd: value_or_None}`` dict. This is the hot path used
    by ``fetch_weather.build_history_window`` to populate the 40-day history
    frame without a per-day HTTP loop (previous behaviour fired 40+ calls
    per manual risk check).

    A range that straddles the archive/forecast cutover is split into two
    calls — still at most two HTTP round trips, not forty.
    """
    start = pd.to_datetime(start_date).date()
    end = pd.to_datetime(end_date).date()
    if start > end:
        return {}
    today = istanbul_today()

    # Split on the archive/forecast boundary. The archive endpoint only has
    # historical data up to "yesterday"; "today and after" lives on the
    # forecast endpoint.
    segments: list[tuple[str, str, str]] = []
    if start < today:
        archive_end = min(end, today - pd.Timedelta(days=1).to_pytimedelta())
        segments.append((ARCHIVE_URL, str(start), str(archive_end)))
    if end >= today:
        forecast_start = max(start, today)
        segments.append((FORECAST_URL, str(forecast_start), str(end)))

    out: dict[str, float | None] = {}
    for url, seg_start, seg_end in segments:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "start_date": seg_start,
            "end_date": seg_end,
            "daily": DAILY_VAR,
        }
        try:
            payload = _request_json(url, params)
        except Exception:
            # Don't let a single upstream blip tank the entire history
            # window — we'll fall back to None for that segment and the
            # hourly fallback path handles the single-day target case.
            continue
        daily = payload.get("daily", {})
        times = daily.get("time", [])
        values = daily.get(DAILY_VAR, [])
        for t, v in zip(times, values):
            out[str(t)] = float(v) if v is not None else None
    return out


@lru_cache(maxsize=256)
def _cached_daily_soil_moisture(
    target_date: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> float | None:
    url = _pick_source(target_date)
    params = {
        "latitude": latitude, "longitude": longitude, "timezone": timezone,
        "start_date": target_date, "end_date": target_date,
        "daily": DAILY_VAR,
    }
    payload = _request_json(url, params)
    values = payload.get("daily", {}).get(DAILY_VAR, [])
    if values and values[0] is not None:
        return float(values[0])
    return None


def fetch_daily_soil_moisture(
    target_date: str,
    latitude: float = LATITUDE,
    longitude: float = LONGITUDE,
    timezone: str = TIMEZONE,
) -> float | None:
    """Single-day fetch — kept for the hourly-fallback branch and tests."""
    return _cached_daily_soil_moisture(target_date, latitude, longitude, timezone)


def fetch_hourly_soil_layers(
    target_date: str,
    latitude: float = LATITUDE,
    longitude: float = LONGITUDE,
    timezone: str = TIMEZONE,
) -> pd.DataFrame:
    url = _pick_source(target_date)
    params = {
        "latitude": latitude, "longitude": longitude, "timezone": timezone,
        "start_date": target_date, "end_date": target_date,
        "hourly": ",".join(HOURLY_LAYERS),
    }
    payload = _request_json(url, params)
    df = pd.DataFrame(payload.get("hourly", {}))
    if not df.empty:
        df["time"] = pd.to_datetime(df["time"])
    return df


def compute_soil_moisture_fallback(hourly_df: pd.DataFrame) -> float | None:
    if hourly_df.empty:
        return None
    if any(c not in hourly_df.columns for c in HOURLY_LAYERS):
        return None
    if hourly_df[HOURLY_LAYERS].isna().all().all():
        return None
    sm_0_1 = hourly_df["soil_moisture_0_to_1cm"].astype(float)
    sm_1_3 = hourly_df["soil_moisture_1_to_3cm"].astype(float)
    sm_3_9 = hourly_df["soil_moisture_3_to_9cm"].astype(float)
    value = float(((1 * sm_0_1 + 2 * sm_1_3 + 4 * sm_3_9) / 7.0).mean(skipna=True))
    return None if pd.isna(value) else value


def resolve_soil_moisture(
    target_date: str,
    latitude: float = LATITUDE,
    longitude: float = LONGITUDE,
    timezone: str = TIMEZONE,
) -> float:
    """Resolve soil_moisture_0_to_7cm_mean: try daily first, fall back to hourly layers."""
    direct = fetch_daily_soil_moisture(target_date, latitude, longitude, timezone)
    if direct is not None:
        return direct
    hourly = fetch_hourly_soil_layers(target_date, latitude, longitude, timezone)
    fallback = compute_soil_moisture_fallback(hourly)
    if fallback is not None:
        return fallback
    raise ValueError(f"soil_moisture could not be resolved for {target_date}")
