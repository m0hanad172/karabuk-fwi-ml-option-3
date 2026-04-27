"""Monitoring / detection endpoints.

This router is **strictly separate** from the Option 3 risk/prediction path.
It never touches ``run_history``, ``predicted_fwi``, or ``high_risk_flag``.

Namespace layout:
  - ``/monitoring/cameras``                       — list + status
  - ``/monitoring/cameras/{cam_id}/start|stop``   — control
  - ``/monitoring/cameras/{cam_id}/feed``         — MJPEG stream
  - ``/monitoring/cameras/{cam_id}/status``       — JSON state
  - ``/monitoring/drone/start|stop``              — control
  - ``/monitoring/drone/feed``                    — MJPEG stream
  - ``/monitoring/drone/status``                  — JSON state
  - ``/monitoring/notifications``                 — recent fire-detection alerts
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.monitoring import cameras as cams
from src.monitoring import drone as drn
from src.monitoring import notifications as notif

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

_MJPEG_MEDIA = "multipart/x-mixed-replace; boundary=frame"


# --- Cameras ---------------------------------------------------------------


@router.get("/cameras", summary="List cameras and their status")
async def list_cameras():
    return {"cameras": cams.list_cameras()}


@router.get(
    "/cameras/devices",
    summary="Probe local camera indices and report which ones actually open",
)
async def camera_devices():
    """Return a list of ``{index, opened, width, height, fps, assigned_to}``.

    Powers the Devices Detected strip on the Monitoring tab so the
    operator can see which camera slots are physically connected without
    needing to restart the backend after plugging in a webcam.
    """
    return {
        "devices": cams.discover_devices(),
        "inference_stride": cams.INFERENCE_STRIDE,
        "capture_fps_cap": cams.CAPTURE_FPS_CAP,
    }


@router.post(
    "/cameras/{cam_id}/remap",
    summary="Change a camera's OpenCV device index at runtime",
)
async def remap_camera(cam_id: str, new_index: int = Query(..., ge=0, le=10)):
    if cam_id not in cams.CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")
    cams.remap_camera(cam_id, new_index)
    return {"cam_id": cam_id, "remapped": True, **cams.get_camera_status(cam_id)}


@router.post(
    "/cameras/auto-detect",
    summary="Probe local indices and auto-assign Logitech BRIO 100 to webcam",
)
async def auto_detect_cameras():
    """Run the resolution-based auto-detect. Highest-resolution opened
    index becomes ``webcam`` (the BRIO 100 reports 1080p on DSHOW), the
    next one becomes ``pc_camera``. Running cameras are stopped first;
    the operator starts them again manually."""
    return cams.auto_detect_cameras()


@router.get("/cameras/{cam_id}/status", summary="Camera status")
async def camera_status(cam_id: str):
    status = cams.get_camera_status(cam_id)
    if not status.get("exists"):
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")
    return status


@router.post("/cameras/{cam_id}/start", summary="Start a camera capture loop")
async def start_camera(cam_id: str):
    if cam_id not in cams.CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")
    ok = cams.start_camera(cam_id)
    return {"cam_id": cam_id, "started": ok, **cams.get_camera_status(cam_id)}


@router.post("/cameras/{cam_id}/stop", summary="Stop a camera capture loop")
async def stop_camera(cam_id: str):
    if cam_id not in cams.CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")
    cams.stop_camera(cam_id)
    return {"cam_id": cam_id, "stopped": True, **cams.get_camera_status(cam_id)}


@router.get("/cameras/{cam_id}/feed", summary="Camera MJPEG feed")
async def camera_feed(cam_id: str):
    if cam_id not in cams.CAMERAS:
        raise HTTPException(status_code=404, detail=f"Camera {cam_id} not found")
    return StreamingResponse(cams.mjpeg_generator(cam_id), media_type=_MJPEG_MEDIA)


# --- Drone -----------------------------------------------------------------


@router.get("/drone/status", summary="Drone feed status")
async def drone_status():
    return drn.get_drone_status()


@router.post("/drone/start", summary="Start the drone feed")
async def drone_start():
    return drn.start_drone()


@router.post("/drone/stop", summary="Stop the drone feed")
async def drone_stop():
    return drn.stop_drone()


@router.get("/drone/feed", summary="Drone MJPEG feed")
async def drone_feed():
    return StreamingResponse(drn.mjpeg_generator(), media_type=_MJPEG_MEDIA)


# --- Notifications ---------------------------------------------------------


@router.get("/notifications", summary="Recent fire-detection notifications")
async def notifications(limit: int = Query(50, ge=1, le=200)):
    return {"notifications": notif.get_notifications(limit=limit)}


# --- Detection alerts (durable evidence log) ------------------------------
#
# These three endpoints read from the append-only JSONL evidence log at
# ``data/notifications/alerts.jsonl``. They are strictly detection-side —
# they never touch ``run_history`` or the Option 3 prediction layer.


@router.get("/alerts", summary="List durable detection alerts (evidence log)")
async def list_alerts(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source: str | None = Query(
        None,
        description="Optional source filter — drone / webcam / pc_camera",
    ),
):
    return {
        "alerts": notif.list_alerts(limit=limit, offset=offset, source=source),
    }


@router.get(
    "/alerts/summary",
    summary="Aggregate stats across the full detection evidence log",
)
async def alerts_summary():
    return notif.alerts_summary()


@router.get(
    "/alerts/{alert_id}",
    summary="Fetch a single detection alert by id (with bbox list)",
)
async def alert_detail(alert_id: str):
    alert = notif.get_alert_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert
