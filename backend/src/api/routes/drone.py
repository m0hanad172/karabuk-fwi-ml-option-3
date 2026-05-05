"""Drone-ready policy and operator-controlled hardware endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.db.database import get_system_state
from src.drone.models import DemoPatrolRequest, ManualDroneCommand
from src.drone.service import DroneSafetyError, get_drone_service

router = APIRouter(prefix="/drone", tags=["drone"])
_MJPEG_MEDIA = "multipart/x-mixed-replace; boundary=frame"


@router.get("/state", summary="Get current drone state")
async def drone_state():
    """Get the latest drone state from the most recent risk check."""
    state = get_system_state("latest_drone_state")
    if state is None:
        return {
            "active_alert_window": False,
            "drone_status": "NO_DATA",
            "drone_interval_minutes": None,
            "next_launch_time": None,
            "reason": "No risk check has been run yet",
        }
    return state


@router.get("/status", summary="Get operator-controlled drone adapter status")
async def drone_status():
    return get_drone_service().get_status()


@router.post("/connect", summary="Connect the configured drone adapter")
async def drone_connect():
    return get_drone_service().connect()


@router.post("/disconnect", summary="Disconnect the configured drone adapter")
async def drone_disconnect():
    return get_drone_service().disconnect()


@router.post("/stream/start", summary="Start drone/video stream")
async def drone_stream_start():
    try:
        return get_drone_service().start_stream()
    except DroneSafetyError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/stream/stop", summary="Stop drone/video stream")
async def drone_stream_stop():
    return get_drone_service().stop_stream()


@router.get("/feed", summary="Drone/video MJPEG feed")
async def drone_feed():
    return StreamingResponse(
        get_drone_service().mjpeg_generator(),
        media_type=_MJPEG_MEDIA,
    )


@router.post("/manual-command", summary="Send an operator-confirmed manual command")
async def drone_manual_command(req: ManualDroneCommand):
    try:
        return get_drone_service().manual_command(
            req.command,
            operator_confirmed=req.operator_confirmed,
        )
    except DroneSafetyError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/emergency-stop", summary="Emergency stop the drone adapter")
async def drone_emergency_stop():
    return get_drone_service().emergency_stop()


@router.post("/demo-patrol", summary="Run demo-only drone patrol")
async def drone_demo_patrol(req: DemoPatrolRequest):
    """Demo-only patrol trigger.

    This endpoint is separate from production wildfire risk decisions. It never
    writes fake risk checks into run_history and never lowers the high-risk
    threshold.
    """
    return get_drone_service().demo_patrol(
        mode=req.mode,
        operator_confirmed=req.operator_confirmed,
    )


@router.get("/patrol/state", summary="Drone patrol recommendation state")
async def drone_patrol_state():
    return get_drone_service().patrol_state(get_system_state("latest_drone_state"))
