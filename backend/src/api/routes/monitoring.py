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

from src.api.runtime_config import demo_alerts_enabled
from src.drone.service import DroneSafetyError
from src.monitoring import cameras as cams
from src.monitoring import drone as drn
from src.monitoring import notifications as notif

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _demo_alerts_enabled() -> bool:
    """Whether ``POST /monitoring/alerts/test`` is wired up.

    Default: enabled. Production deployments that don't want a
    public test endpoint can set ``DEMO_ALERTS_ENABLED=false``
    (or ``BACKEND_ENV=production`` without explicitly enabling it).

    The frontend reads the same flag through ``GET /system/config`` so
    the Detection Alerts tab and this endpoint enable/disable together.
    """
    return demo_alerts_enabled()

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
        "runtime": cams.runtime_context(),
    }


@router.get(
    "/runtime",
    summary="Where the backend is running (host OS / inside Docker / "
            "camera passthrough supported?)",
)
async def monitoring_runtime():
    """Tiny helper the Monitoring tab calls so it can render the
    correct unavailable-camera copy.

    Returns:
      ``in_docker``                       — boolean
      ``host_os``                         — "windows" / "posix"
      ``camera_passthrough_supported``    — false on "Docker Desktop
                                            on Windows", true everywhere
                                            host cameras can be reached
    """
    return cams.runtime_context()


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
    status = cams.get_camera_status(cam_id)
    if not status.get("running"):
        detail = "Camera feed is stopped. Start the camera before opening the feed."
        if status.get("last_error"):
            detail = status["last_error"]
            raise HTTPException(status_code=503, detail=detail)
        raise HTTPException(status_code=409, detail=detail)
    return StreamingResponse(cams.mjpeg_generator(cam_id), media_type=_MJPEG_MEDIA)


# --- Drone -----------------------------------------------------------------


@router.get("/drone/status", summary="Drone feed status")
async def drone_status():
    return drn.get_drone_status()


@router.post("/drone/start", summary="Start the drone feed")
async def drone_start():
    try:
        return drn.start_drone()
    except DroneSafetyError as e:
        raise HTTPException(status_code=403, detail=str(e))


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
# These endpoints read/write the SQLite ``detection_alerts`` table.
# Snapshot files remain on disk under ``data/notifications``. They are
# strictly detection-side and never touch ``run_history`` or the Option
# 3 prediction layer.


@router.get("/alerts", summary="List durable detection alerts (evidence log)")
async def list_alerts(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source: str | None = Query(
        None,
        description="Optional source filter — drone / webcam / pc_camera / demo",
    ),
    read_filter: str | None = Query(
        None,
        alias="filter",
        pattern="^(all|unread|read)$",
        description=(
            "Optional read-state filter: 'all' (default), 'unread', or 'read'. "
            "Backed by the detection_alerts.is_read column."
        ),
    ),
):
    return {
        "alerts": notif.list_alerts(
            limit=limit, offset=offset, source=source, read_filter=read_filter
        ),
    }


@router.get(
    "/alerts/summary",
    summary="Aggregate stats across the full detection evidence log",
)
async def alerts_summary():
    return notif.alerts_summary()


@router.get(
    "/alerts/latest",
    summary="Most recently raised detection alert (or null)",
)
async def alerts_latest():
    """Return the single most recent alert, or ``{"alert": null}`` if none.

    Routed BEFORE ``/alerts/{alert_id}`` so FastAPI does not try to
    match ``"latest"`` as an alert id. The dashboard polls this every
    few seconds to drive the visible in-app notification banner — a
    cheap GET that lets the UI react immediately to a new detection.
    """
    return {"alert": notif.latest_alert()}


@router.post(
    "/alerts/test",
    summary="Append a synthetic detection alert (demo / smoke-test)",
)
async def alerts_test(
    label: str = Query(
        "fire",
        description="Detection label — fire or smoke (anything else collapses to fire).",
    ),
    confidence: float = Query(
        0.78, ge=0.0, le=1.0, description="Synthetic confidence in [0,1]."
    ),
    source: str = Query(
        "demo",
        description=(
            "Source tag — defaults to 'demo' so synthetic alerts are easy "
            "to filter out later. Pass webcam/pc_camera/drone to simulate "
            "a hardware-raised alert."
        ),
    ),
):
    """Create a synthetic alert through the real persistence path.

    Useful when no camera / drone hardware is available — the alert
    lands in SQLite and the in-memory ring buffer
    just like a real YOLO detection, so you can verify the Detection
    Alerts tab, the dashboard banner, and ``/alerts/summary`` all
    react correctly. Demo alerts persist across backend restarts in
    the runtime SQLite database.

    Returns 404 when ``DEMO_ALERTS_ENABLED=false`` (or under
    ``BACKEND_ENV=production`` without an explicit enable) so the
    endpoint is invisible to a production OpenAPI consumer.
    """
    if not _demo_alerts_enabled():
        raise HTTPException(
            status_code=404,
            detail=(
                "Demo alerts are disabled in this environment. "
                "Set DEMO_ALERTS_ENABLED=true (or BACKEND_ENV=development) "
                "to re-enable."
            ),
        )
    return notif.add_demo_alert(
        label=label, confidence=confidence, source=source
    )


@router.post(
    "/alerts/mark-all-read",
    summary="Mark every detection alert as read",
)
async def alerts_mark_all_read():
    """Flip every currently-unread alert to read in one shot.

    Returns the count of alerts whose state actually changed (the
    "Marked N alert(s) as read." copy on the frontend uses this).
    Listed BEFORE the ``/alerts/{alert_id}`` route so FastAPI does not
    interpret ``"mark-all-read"`` as an alert id.
    """
    flipped = notif.mark_all_alerts_read()
    return {"flipped": flipped}


@router.post(
    "/alerts/{alert_id}/read",
    summary="Mark a single detection alert as read",
)
async def alert_mark_read(alert_id: str):
    alert = notif.mark_alert_read(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert


@router.post(
    "/alerts/{alert_id}/unread",
    summary="Re-flag a previously-read alert as unread",
)
async def alert_mark_unread(alert_id: str):
    alert = notif.mark_alert_unread(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert


@router.delete(
    "/alerts/{alert_id}",
    summary="Soft-delete one detection alert from dashboard views",
)
async def alert_delete(alert_id: str):
    deleted = notif.delete_alert(alert_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return deleted


@router.get(
    "/alerts/{alert_id}",
    summary="Fetch a single detection alert by id (with bbox list)",
)
async def alert_detail(alert_id: str):
    alert = notif.get_alert_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert
