"""Pydantic schemas for API request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ManualRunRequest(BaseModel):
    target_date: str | None = Field(None, description="Target date (YYYY-MM-DD). Defaults to today.")
    allow_drone_trigger: bool = Field(False, description="Whether this manual run can trigger drone alerts.")


class PredictionResult(BaseModel):
    run_id: str
    run_type: str
    run_timestamp: str
    target_date: str
    predicted_fwi: float
    high_risk_probability: float
    high_risk_flag: int
    decision_reason: str
    thresholds: dict


class RunHistoryEntry(BaseModel):
    run_id: str
    run_type: str
    run_timestamp: str
    target_date: str
    predicted_fwi: float | None
    high_risk_probability: float | None
    high_risk_flag: int | None
    decision_reason: str | None
    drone_triggered: int | None


class LiveWeatherSnapshot(BaseModel):
    source: str
    source_time: str | None
    fetch_time: str
    display_timezone: str
    temperature_now: float | None
    rh_now: float | None
    ws_now: float | None
    precip_now: float | None
    cloud_cover_now: float | None
    is_display_only: bool = True


class DroneState(BaseModel):
    active_alert_window: bool
    drone_status: str
    drone_interval_minutes: int | None
    next_launch_time: str | None
    reason: str


class ModelInfo(BaseModel):
    stage1_model: str
    stage2_model: str
    n_training_features: int
    stage2_input_features: list[str]
    thresholds: dict
    stage1_test_metrics: dict | None
    stage2_test_metrics: dict | None


class HealthStatus(BaseModel):
    status: str
    stage1_model_loaded: bool
    stage2_model_loaded: bool
    database_ok: bool
    timestamp: str
