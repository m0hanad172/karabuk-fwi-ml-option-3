"""
Live inference orchestrator.

Orchestrates: fetch weather → build features → stacked predict → persist result.
Used by both scheduled runs and manual checks.

All outputs are JSON-safe (no pandas Timestamps, no numpy scalars) so the
result dict can be returned directly from a FastAPI route without a custom
encoder. Drone state is *only* allowed to activate for operational runs
(`manual` / `scheduled`); test / evaluation runs always return a STANDBY
drone_state regardless of their predicted FWI.
"""
from __future__ import annotations

import uuid

import pandas as pd

from configs.settings import MANUAL_CHECK_CAN_TRIGGER_DRONE_DEFAULT
from src.api.json_safe import to_json_safe
from src.api.run_types import (
    RUN_TYPE_MANUAL,
    is_operational,
    normalize_run_type,
)
from src.api.time_utils import istanbul_now_iso, istanbul_today_str
from src.data.fetch_weather import build_history_window, fetch_model_input_for_date
from src.features.build_features import build_feature_row_from_raw_inputs
from src.features.feature_schema import TRAINING_FEATURES
from src.features.feature_validator import validate_feature_row
from src.inference.predict import predict_from_features
from src.pipeline.drone_logic import compute_drone_state


def run_risk_check(
    target_date: str | None = None,
    run_type: str = RUN_TYPE_MANUAL,
    allow_drone_trigger: bool | None = None,
) -> dict:
    """
    Execute a full stacked risk check for a given date.

    This fetches fresh model-input weather (NOT live display data),
    builds features, runs the stacked pipeline, and returns the result.
    The returned dict is fully JSON-safe.
    """
    run_type = normalize_run_type(run_type)
    operational = is_operational(run_type)

    if allow_drone_trigger is None:
        allow_drone_trigger = MANUAL_CHECK_CAN_TRIGGER_DRONE_DEFAULT
    # Hard guard: evaluation/test runs can NEVER trigger the drone,
    # regardless of what the caller passed.
    if not operational:
        allow_drone_trigger = False

    # Operational calendar runs on Istanbul local days (not UTC days).
    # Near midnight Istanbul the UTC date is already the previous day,
    # which previously caused the pipeline to query the wrong target.
    if target_date is None:
        target_date = istanbul_today_str()

    run_id = uuid.uuid4().hex[:12]
    # Tz-aware Istanbul ISO 8601 so the browser can round-trip the string
    # without falling back to "naive == local" parsing.
    run_timestamp = istanbul_now_iso()

    # Fetch model-input weather (separate from live display)
    raw_row = fetch_model_input_for_date(target_date)
    history_df = build_history_window(target_date)

    # Build features
    feature_row = build_feature_row_from_raw_inputs(raw_row, history_df)

    # Validate
    validation = validate_feature_row(feature_row, TRAINING_FEATURES)
    if not validation["is_valid"]:
        raise ValueError(f"Feature validation failed: {validation}")

    # Stacked prediction
    prediction = predict_from_features(feature_row)

    # Drone state (only operational runs may activate)
    drone_state = compute_drone_state(
        prediction, allow_drone_trigger=allow_drone_trigger
    )

    # Raw inputs used (for audit) — sanitized to pure JSON types
    raw_inputs_raw = raw_row.to_dict(orient="records")[0] if not raw_row.empty else {}
    raw_inputs = to_json_safe(raw_inputs_raw)

    # Engineered features used (for audit)
    feature_values = {
        col: float(feature_row[col].iloc[0]) if col in feature_row.columns else None
        for col in TRAINING_FEATURES
    }

    result = {
        "run_id": run_id,
        "run_type": run_type,
        "run_timestamp": run_timestamp,
        "target_date": target_date,
        **prediction,
        "drone_state": drone_state,
        "validation": validation,
        "raw_inputs": raw_inputs,
        "feature_values": feature_values,
    }

    # Final safety net: coerce anything the prediction layer may have
    # smuggled in (numpy scalars, etc.) to plain JSON types.
    return to_json_safe(result)
