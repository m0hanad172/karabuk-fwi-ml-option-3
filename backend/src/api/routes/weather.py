"""Live weather display endpoints — display-only, NOT model input."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.services.weather_service import get_live_weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/live", summary="Get current weather snapshot (display-only)")
async def live_weather():
    """
    Fetch current weather for dashboard display cards.
    This data is display-only and must NOT be used as model input.
    """
    try:
        return get_live_weather()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {e}")
