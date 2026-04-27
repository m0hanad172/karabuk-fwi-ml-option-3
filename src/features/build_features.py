"""
Feature engineering for Karabuk FWI ML Option 3.

Adapted from old project. Changes:
  - Removed days_since_last_rain (duplicate of consecutive_dry_days)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def saturation_vapor_pressure(temp_c: pd.Series) -> pd.Series:
    return 0.6108 * np.exp(17.27 * temp_c / (temp_c + 237.3))


def build_final_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy().sort_values("date").reset_index(drop=True)

    # Normalise column names if coming from raw CSV with different casing
    if "temperature" not in d.columns:
        d["temperature"] = d["Temperature"].astype(float)
        d["rh"] = d["RH"].astype(float)
        d["ws"] = d["Ws"].astype(float)
        d["precip"] = d["Precipitation"].astype(float)

    # Seasonal encoding
    d["dayofyear"] = pd.to_datetime(d["date"]).dt.dayofyear
    d["doy_sin"] = np.sin(2 * np.pi * d["dayofyear"] / 366.0)
    d["doy_cos"] = np.cos(2 * np.pi * d["dayofyear"] / 366.0)
    d["month_sin"] = np.sin(2 * np.pi * d["month"] / 12.0)
    d["month_cos"] = np.cos(2 * np.pi * d["month"] / 12.0)

    # Derived weather features
    d["es"] = saturation_vapor_pressure(d["temperature"])
    d["vpd"] = d["es"] * (1 - d["rh"] / 100.0)
    d["fuel_drying_rate"] = d["temperature"] * (1 - d["rh"] / 100.0)
    d["hdw"] = d["vpd"] * d["ws"]
    d["wind_squared"] = d["ws"] ** 2
    d["dew_point"] = d["temperature"] - ((100 - d["rh"]) / 5.0)

    # Shifted series to prevent look-ahead leakage in rolling features
    temp_prev = d["temperature"].shift(1)
    rh_prev = d["rh"].shift(1)
    ws_prev = d["ws"].shift(1)
    precip_prev = d["precip"].shift(1)

    # Rolling precipitation memory
    for w in [3, 7, 30]:
        d[f"precip_sum_{w}d"] = precip_prev.rolling(w, min_periods=1).sum()

    # Rolling temperature memory
    for w in [3, 7]:
        d[f"t_mean_{w}d"] = temp_prev.rolling(w, min_periods=1).mean()

    # Rolling humidity memory
    for w in [3, 7]:
        d[f"rh_min_{w}d"] = rh_prev.rolling(w, min_periods=1).min()
        d[f"rh_mean_{w}d"] = rh_prev.rolling(w, min_periods=1).mean()

    # Rolling wind memory
    for w in [3, 7]:
        d[f"ws_mean_{w}d"] = ws_prev.rolling(w, min_periods=1).mean()
        d[f"ws_max_{w}d"] = ws_prev.rolling(w, min_periods=1).max()

    # EWMA memory
    d["ewma_t"] = temp_prev.ewm(alpha=0.3, adjust=False).mean()
    d["ewma_rh"] = rh_prev.ewm(alpha=0.5, adjust=False).mean()
    d["ewma_precip"] = precip_prev.ewm(alpha=0.7, adjust=False).mean()

    # Consecutive dry days
    streaks = []
    streak = 0
    for p in precip_prev.fillna(0):
        streak = streak + 1 if p <= 0 else 0
        streaks.append(streak)
    d["consecutive_dry_days"] = streaks

    # Classification target
    if "target_ge_35" not in d.columns and "FWI" in d.columns:
        d["target_ge_35"] = (d["FWI"] >= 35).astype(int)

    return d


def build_feature_row_from_raw_inputs(
    raw_row: pd.DataFrame, history_df: pd.DataFrame
) -> pd.DataFrame:
    """Build a single feature row for inference by combining history + today's raw inputs."""
    combined = pd.concat([history_df.copy(), raw_row.copy()], ignore_index=True)
    combined = (
        combined.sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )
    featured = build_final_features(combined)
    target_date = pd.to_datetime(raw_row["date"].iloc[0])
    row = featured[featured["date"] == target_date].copy()
    if row.empty:
        raise ValueError(f"No feature row generated for target_date={target_date.date()}")
    return row
