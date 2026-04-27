"""
Locked feature schema for Karabuk FWI ML Option 3.

Total training features: 34
  - 8 raw API features
  - 26 engineered features

Removed: days_since_last_rain (duplicate of consecutive_dry_days)
"""

RAW_API_FEATURES = [
    "temperature",
    "rh",
    "ws",
    "precip",
    "cloud_cover_mean",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
    "soil_moisture_0_to_7cm_mean",
]

ENGINEERED_FEATURES = [
    # Seasonal encoding
    "doy_sin", "doy_cos", "month_sin", "month_cos",
    # Derived weather
    "vpd", "fuel_drying_rate", "hdw", "wind_squared", "dew_point",
    # Rolling precipitation memory
    "precip_sum_3d", "precip_sum_7d", "precip_sum_30d",
    # Rolling temperature memory
    "t_mean_3d", "t_mean_7d",
    # Rolling humidity memory
    "rh_min_3d", "rh_min_7d", "rh_mean_3d", "rh_mean_7d",
    # Rolling wind memory
    "ws_mean_3d", "ws_mean_7d", "ws_max_3d", "ws_max_7d",
    # EWMA memory
    "ewma_t", "ewma_rh", "ewma_precip",
    # Dryness
    "consecutive_dry_days",
]

TRAINING_FEATURES = RAW_API_FEATURES + ENGINEERED_FEATURES

# Stage 2 support features — locked after ablation.
# Ablation result: predicted_fwi + rh + ws + fuel_drying_rate gave best
# precision (0.333) at perfect recall (1.000) on 2024 validation.
STAGE2_SUPPORT_FEATURES = ["rh", "ws", "fuel_drying_rate"]

# Full Stage 2 input = predicted_fwi (from Stage 1) + support features
STAGE2_INPUT_FEATURES = ["predicted_fwi"] + STAGE2_SUPPORT_FEATURES

NON_TRAINING_COLUMNS = [
    "day", "month", "year", "date", "FWI", "target_ge_35", "dayofyear", "es",
]

assert len(RAW_API_FEATURES) == 8, f"Expected 8 raw features, got {len(RAW_API_FEATURES)}"
assert len(ENGINEERED_FEATURES) == 26, f"Expected 26 engineered features, got {len(ENGINEERED_FEATURES)}"
assert len(TRAINING_FEATURES) == 34, f"Expected 34 training features, got {len(TRAINING_FEATURES)}"
