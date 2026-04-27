"""Risk check and prediction endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.api.db.models import ManualRunRequest
from src.api.run_types import RUN_TYPE_MANUAL
from src.api.services.risk_service import execute_risk_check, get_latest_prediction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/check", summary="Run a manual risk check")
async def manual_risk_check(req: ManualRunRequest):
    """
    Execute a full stacked risk check.

    Fetches fresh model-input weather, builds features, runs Stage 1 + Stage 2.
    This endpoint always runs as an OPERATIONAL `manual` run. It can
    update the live Latest Model Result card and may trigger the drone
    policy if ``allow_drone_trigger`` is true.
    """
    try:
        result = execute_risk_check(
            target_date=req.target_date,
            run_type=RUN_TYPE_MANUAL,
            allow_drone_trigger=req.allow_drone_trigger,
        )
        return result
    except ValueError as e:
        # Feature validation / missing data — client-visible message
        logger.warning("Manual risk check rejected: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Manual risk check failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.get("/latest", summary="Get latest operational prediction result")
async def latest_prediction():
    """
    Get the most recent OPERATIONAL prediction (manual or scheduled).

    Test / evaluation runs are deliberately excluded so they can never
    appear as the live Latest Model Result on the dashboard.
    """
    result = get_latest_prediction()
    if result is None:
        raise HTTPException(status_code=404, detail="No operational predictions yet")
    return result
