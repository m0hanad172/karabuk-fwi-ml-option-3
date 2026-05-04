"""
Model-input weather fetching from Open-Meteo.
Strictly for model pipeline — NOT for live display.

Adapted from old project with cleaner separation.

Phase 5 perf work
-----------------
The previous implementation populated ``soil_moisture_0_to_7cm_mean`` for
the 40-day history window with a per-day Python list comprehension that
fired one Open-Meteo request per row. That single decision accounted for
~28 s of the ~30 s wall-clock of a manual risk check.

The window fetch now issues ONE range call to
``soil_moisture.fetch_daily_soil_moisture_range`` and indexes into the
returned dict by date. Missing values fall back to the single-day hourly
resolver, which is rare (only when Open-Meteo returns no daily layer for
that specific date).

HTTP timeouts are also tightened from 60 s → 15 s — the manual risk
check is an interactive path and should fail fast, not hang for a minute
on a stalled upstream.
"""
from __future__ import annotations

import requests
import pandas as pd
from datetime import timedelta

from configs.settings import LATITUDE, LONGITUDE, TIMEZONE, HISTORY_WINDOW_DAYS
from src.api.time_utils import istanbul_today
from src.data.soil_moisture import (
    fetch_daily_soil_moisture_range,
    resolve_soil_moisture,
)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_HTTP_TIMEOUT = 15

# Daily aggregate inputs only. These variables must match the training CSV
# semantics: daily max temperature, daily min RH, daily max wind, daily
# precipitation sum, mean cloud cover, solar radiation sum, ET0, and daily
# soil moisture mean. Do not replace them with current-hour weather
# variables unless the model is retrained.
DAILY_MODEL_INPUT_VARS = [
    "temperature_2m_max",
    "relative_humidity_2m_min",
    "wind_speed_10m_max",
    "precipitation_sum",
    "cloud_cover_mean",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
]

RENAME_MAP = {
    "temperature_2m_max": "temperature",
    "relative_humidity_2m_min": "rh",
    "wind_speed_10m_max": "ws",
    "precipitation_sum": "precip",
}


def _request_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=_HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _pick_source(target_date: str) -> str:
    # Istanbul-local "today" so the archive/forecast cutover matches the
    # Karabük operational calendar, not the UTC one.
    today = istanbul_today()
    return FORECAST_URL if pd.to_datetime(target_date).date() >= today else ARCHIVE_URL


def _daily_to_frame(payload: dict) -> pd.DataFrame:
    daily = pd.DataFrame(payload["daily"])
    daily["date"] = pd.to_datetime(daily["time"])
    daily = daily.drop(columns=["time"])
    daily = daily.rename(columns=RENAME_MAP)
    daily["day"] = daily["date"].dt.day
    daily["month"] = daily["date"].dt.month
    daily["year"] = daily["date"].dt.year
    return daily


def _attach_soil_moisture_batch(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> pd.DataFrame:
    """Populate ``soil_moisture_0_to_7cm_mean`` for a date range using a
    single Open-Meteo call. Fills missing rows with the hourly-fallback
    resolver one at a time — usually zero rows on a healthy upstream."""
    if df.empty:
        return df
    sm_map = fetch_daily_soil_moisture_range(
        start_date, end_date, latitude, longitude, timezone
    )
    # Normalise dict keys to yyyy-mm-dd strings (Open-Meteo already does).
    def _lookup(d: pd.Timestamp) -> float | None:
        return sm_map.get(str(d.date()))

    df = df.copy()
    df["soil_moisture_0_to_7cm_mean"] = df["date"].map(_lookup)

    # Rare fallback: any row that didn't come back from the range call
    # (Open-Meteo gap, nullable upstream field, etc.) gets the full hourly
    # fallback resolver. One HTTP call per missing row, but in practice
    # this is 0 rows on a normal window.
    missing_mask = df["soil_moisture_0_to_7cm_mean"].isna()
    if missing_mask.any():
        filled = []
        for _, row in df[missing_mask].iterrows():
            try:
                filled.append(
                    resolve_soil_moisture(
                        str(row["date"].date()), latitude, longitude, timezone
                    )
                )
            except Exception:
                filled.append(None)
        df.loc[missing_mask, "soil_moisture_0_to_7cm_mean"] = filled
    return df


def fetch_archive_window(
    start_date: str, end_date: str,
    latitude: float = LATITUDE, longitude: float = LONGITUDE, timezone: str = TIMEZONE,
) -> pd.DataFrame:
    params = {
        "latitude": latitude, "longitude": longitude, "timezone": timezone,
        "start_date": start_date, "end_date": end_date,
        "daily": ",".join(DAILY_MODEL_INPUT_VARS),
    }
    payload = _request_json(ARCHIVE_URL, params)
    df = _daily_to_frame(payload)
    return _attach_soil_moisture_batch(
        df, start_date, end_date, latitude, longitude, timezone
    )


def fetch_forecast_window(
    start_date: str, end_date: str,
    latitude: float = LATITUDE, longitude: float = LONGITUDE, timezone: str = TIMEZONE,
) -> pd.DataFrame:
    days = (pd.to_datetime(end_date).date() - pd.to_datetime(start_date).date()).days + 1
    params = {
        "latitude": latitude, "longitude": longitude, "timezone": timezone,
        "forecast_days": max(days, 1),
        "daily": ",".join(DAILY_MODEL_INPUT_VARS),
    }
    payload = _request_json(FORECAST_URL, params)
    df = _daily_to_frame(payload)
    if not df.empty:
        df = df[(df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))].copy()
    return _attach_soil_moisture_batch(
        df, start_date, end_date, latitude, longitude, timezone
    )


def fetch_model_input_for_date(
    target_date: str,
    latitude: float = LATITUDE, longitude: float = LONGITUDE, timezone: str = TIMEZONE,
) -> pd.DataFrame:
    """Fetch a single day's raw model-input weather data."""
    url = _pick_source(target_date)
    if url == FORECAST_URL:
        # Forecast endpoint can't take start/end for a single day — ask for
        # just today's forecast (1 day) instead of the default 16-day window.
        # The row filter below keeps only the target row.
        params = {
            "latitude": latitude, "longitude": longitude, "timezone": timezone,
            "forecast_days": 1,
            "daily": ",".join(DAILY_MODEL_INPUT_VARS),
        }
    else:
        params = {
            "latitude": latitude, "longitude": longitude, "timezone": timezone,
            "start_date": target_date, "end_date": target_date,
            "daily": ",".join(DAILY_MODEL_INPUT_VARS),
        }
    payload = _request_json(url, params)
    df = _daily_to_frame(payload)
    df = df[df["date"] == pd.to_datetime(target_date)].copy()
    if df.empty:
        raise ValueError(f"No model-input data for {target_date}")
    df["soil_moisture_0_to_7cm_mean"] = resolve_soil_moisture(
        target_date, latitude, longitude, timezone
    )
    return df


def build_history_window(
    target_date: str, history_days: int = HISTORY_WINDOW_DAYS,
    latitude: float = LATITUDE, longitude: float = LONGITUDE, timezone: str = TIMEZONE,
) -> pd.DataFrame:
    """Fetch the history window needed for rolling/EWMA feature engineering."""
    target = pd.to_datetime(target_date).date()
    history_start = target - timedelta(days=history_days)
    history_end = target - timedelta(days=1)
    today = istanbul_today()

    frames = []
    if history_start <= min(history_end, today - timedelta(days=1)):
        archive_end = min(history_end, today - timedelta(days=1))
        frames.append(fetch_archive_window(str(history_start), str(archive_end), latitude, longitude, timezone))
    if history_end >= today:
        forecast_start = max(history_start, today)
        frames.append(fetch_forecast_window(str(forecast_start), str(history_end), latitude, longitude, timezone))

    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
