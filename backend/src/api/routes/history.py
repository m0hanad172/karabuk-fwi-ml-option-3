"""Run history, audit, and analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.services.history_service import list_runs, get_run_detail
from src.api.services.analytics_service import get_analytics

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/runs", summary="List run history")
async def run_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return list_runs(limit=limit, offset=offset)


@router.get("/runs/{run_id}", summary="Get full run detail")
async def run_detail(run_id: str):
    result = get_run_detail(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.get("/analytics", summary="Historical FWI analytics from training dataset")
async def analytics():
    return get_analytics()
