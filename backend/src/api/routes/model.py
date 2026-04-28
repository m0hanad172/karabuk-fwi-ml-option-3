"""Model info and system health endpoints."""
from __future__ import annotations

import json
from fastapi import APIRouter

from configs.paths import STAGE1_DIR, STAGE2_DIR, METADATA_DIR
from configs.settings import CLASS_THRESHOLD, NEAR_THRESHOLD, DEFAULT_PROBABILITY_THRESHOLD
from src.features.feature_schema import TRAINING_FEATURES, STAGE2_INPUT_FEATURES
from src.api.db.models import ModelInfo, HealthStatus
from src.api.runtime_config import public_runtime_config
from src.api.services.scheduler import get_scheduler_status
from src.api.time_utils import istanbul_now_iso

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/model", summary="Get model metadata", response_model=ModelInfo)
async def model_info():
    stage1_meta = {}
    stage2_meta = {}
    s1_path = METADATA_DIR / "stage1_metadata.json"
    s2_path = METADATA_DIR / "stage2_metadata.json"
    if s1_path.exists():
        stage1_meta = json.loads(s1_path.read_text(encoding="utf-8"))
    if s2_path.exists():
        stage2_meta = json.loads(s2_path.read_text(encoding="utf-8"))

    return ModelInfo(
        stage1_model="HistGradientBoostingRegressor",
        stage2_model="RandomForestClassifier (stacked)",
        n_training_features=len(TRAINING_FEATURES),
        stage2_input_features=STAGE2_INPUT_FEATURES,
        thresholds={
            "high_threshold": CLASS_THRESHOLD,
            "near_threshold": NEAR_THRESHOLD,
            "probability_threshold": DEFAULT_PROBABILITY_THRESHOLD,
        },
        stage1_test_metrics=stage1_meta.get("test_metrics"),
        stage2_test_metrics=stage2_meta.get("test_metrics"),
    )


@router.get("/health", summary="System health check", response_model=HealthStatus)
async def health_check():
    stage1_ok = (STAGE1_DIR / "histgb_regressor.joblib").exists()
    stage2_ok = (STAGE2_DIR / "rf_classifier_stacked.joblib").exists()
    db_ok = True
    try:
        from src.api.db.database import get_connection
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
    except Exception:
        db_ok = False

    all_ok = stage1_ok and stage2_ok and db_ok
    return HealthStatus(
        status="healthy" if all_ok else "degraded",
        stage1_model_loaded=stage1_ok,
        stage2_model_loaded=stage2_ok,
        database_ok=db_ok,
        timestamp=istanbul_now_iso(),
    )


@router.get("/scheduler", summary="Get scheduler status")
async def scheduler_status():
    return get_scheduler_status()


@router.get(
    "/config",
    summary="Runtime feature flags exposed to the frontend",
)
async def runtime_config():
    """Expose a tiny env-driven feature-flag object to the frontend.

    Today this exposes environment/mode, version, and whether the demo
    / test-alert affordance is enabled. It is the natural place for any
    future frontend-visible toggle (e.g. monitoring hardware hints).

    Why we expose this at runtime instead of baking
    ``NEXT_PUBLIC_*`` build-time vars into the frontend image:
    toggling a build-time var requires a rebuild, but toggling a
    runtime backend env (e.g. before flipping CORS_ORIGINS for
    production) should also flip whether the dashboard offers the
    Test alert button; a single source of truth on the backend
    avoids drift.
    """
    return public_runtime_config()
