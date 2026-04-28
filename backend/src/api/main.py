"""
FastAPI application for Karabuk FWI ML Option 3.

Provides:
  - /risk     — manual risk checks, latest prediction
  - /weather  — live weather display (display-only)
  - /history  — run history and audit
  - /system   — model info, health, scheduler status
  - /drone    — drone state
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from configs.paths import NOTIFICATIONS_DIR
from src.api.db.database import init_db
from src.api.runtime_config import APP_VERSION, resolve_cors_origins
from src.api.services.scheduler import start_scheduler, stop_scheduler
from src.api.routes import risk, weather, history, model, drone, monitoring
from src.inference.predict import get_predictor
from src.monitoring import notifications as notif

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _prewarm_predictor() -> None:
    """Load the stacked predictor artifacts off the main thread.

    The first manual risk check after startup used to pay a one-off ~1–2 s
    model-load cost inline. Doing it in a daemon thread at startup makes
    the first interactive call feel as fast as subsequent ones.
    """
    try:
        predictor = get_predictor()
        predictor._load_models()  # noqa: SLF001 — deliberate warm load
        logger.info("Stacked predictor prewarmed (Stage 1 + Stage 2 loaded)")
    except Exception as e:  # noqa: BLE001
        logger.warning("Predictor prewarm failed (will retry on first call): %s", e)


def _validate_camera_mapping() -> None:
    """Fingerprint-validate the persisted camera mapping in the background.

    Runs a ``discover_devices`` probe and compares each role's saved
    resolution/fps against the live device. Logs a warning for any role
    whose fingerprint changed while the backend was off (device replugged,
    swapped to a different USB port, etc.) so the operator knows to
    re-run auto-detect from the Monitoring tab.

    Strictly advisory — never mutates the mapping. Runs off the main
    thread because the ``cv2.VideoCapture`` probe can take ~200 ms per
    index on Windows and we don't want to block startup.
    """
    try:
        from src.monitoring import camera_mapping
        from src.monitoring.cameras import (
            CAMERAS,
            auto_detect_cameras,
            discover_devices,
        )

        # First-boot bootstrap: without a persisted mapping, the defaults
        # in cameras.py (pc_camera=0, webcam=1) are just a guess about
        # Windows DSHOW enumeration order. On this machine the Logitech
        # BRIO enumerates at index 0, so the guess is wrong and the UI
        # would label BRIO as "PC Camera". Running auto-detect once now
        # binds the logical roles to the correct physical devices by
        # resolution, then persists the mapping so subsequent boots
        # follow the "validate, don't mutate" path below.
        if not camera_mapping.mapping_file_exists():
            logger.info(
                "No persisted camera mapping found — running one-shot "
                "auto-detect to bind roles to physical devices."
            )
            result = auto_detect_cameras()
            logger.info("Startup camera auto-detect result: %s", {
                "changed": result.get("changed"),
                "assignments": result.get("assignments"),
                "brio_detected": result.get("brio_detected"),
            })
            return

        devices = discover_devices()
        stale = camera_mapping.validate_mapping(CAMERAS, devices)
        if stale:
            logger.warning(
                "Persisted camera mapping looks stale for role(s) %s — "
                "re-run auto-detect from the Monitoring tab.", stale,
            )
        else:
            logger.info("Persisted camera mapping validated OK")
        # Always refresh fingerprints on startup so the saved file reflects
        # the latest observed device characteristics (no-op on first boot).
        camera_mapping.apply_discovered_fingerprint(CAMERAS, devices)
    except Exception as e:  # noqa: BLE001 — mapping is advisory only
        logger.warning("Camera mapping validation skipped: %s", e)


def _prewarm_yolo() -> None:
    """Load the YOLO fire detector off the main thread.

    Ultralytics import + weights load is ~2–4 s cold. Without this, the
    first frame delivered by any camera/drone loop paid that cost inline,
    making "Start feed" feel broken for several seconds. Monitoring is
    strictly optional, so any failure is logged and ignored.
    """
    try:
        # Local import keeps the prediction path free of monitoring deps.
        from src.monitoring.yolo_detector import get_detector
        model = get_detector()
        if model is not None:
            logger.info("YOLO fire detector prewarmed")
        else:
            logger.info(
                "YOLO fire detector not available — detection disabled (this is OK)"
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("YOLO prewarm failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Karabuk FWI backend")
    init_db()
    # Rehydrate the in-memory monitoring ring buffer from the on-disk
    # evidence log so the live Monitoring feed and the Detection Alerts
    # tab do not appear empty immediately after a restart. Best-effort:
    # a read failure is logged and the runtime continues with an empty
    # buffer — the evidence log itself is untouched.
    try:
        loaded = notif.hydrate_ring_buffer_from_log()
        if loaded:
            logger.info("Rehydrated %d detection alerts from evidence log", loaded)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not rehydrate alert ring buffer: %s", e)

    # Phase 5: prewarm the heavy singletons in background threads so the
    # first interactive call (manual risk check, first camera frame)
    # doesn't pay their cold-start cost. These threads are daemons — they
    # never block startup and never crash the API.
    threading.Thread(target=_prewarm_predictor, name="prewarm-predictor",
                     daemon=True).start()
    threading.Thread(target=_prewarm_yolo, name="prewarm-yolo",
                     daemon=True).start()
    threading.Thread(target=_validate_camera_mapping,
                     name="validate-camera-mapping", daemon=True).start()

    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Karabuk FWI backend stopped")


app = FastAPI(
    title="Karabuk FWI Wildfire Risk Prediction API",
    description="Option 3 Stacked Architecture — regression backbone with safety classifier support",
    version=APP_VERSION,
    lifespan=lifespan,
)


def _resolve_cors_origins() -> list[str]:
    """Resolve the CORS allow-list from env-safe runtime defaults."""
    origins = resolve_cors_origins()
    return origins


_cors_origins = _resolve_cors_origins()
# allow_credentials=True is incompatible with allow_origins=["*"] per the
# CORS spec; fall back gracefully so a misconfigured deploy still works.
_cors_credentials = "*" not in _cors_origins
logger.info("CORS allow_origins=%s allow_credentials=%s", _cors_origins, _cors_credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(risk.router)
app.include_router(weather.router)
app.include_router(history.router)
app.include_router(model.router)
app.include_router(drone.router)
app.include_router(monitoring.router)

# Notification snapshots are served as static files under /static/notifications.
# Monitoring is strictly detection-only and never writes to the prediction path.
NOTIFICATIONS_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/notifications",
    StaticFiles(directory=str(NOTIFICATIONS_DIR)),
    name="notifications",
)


@app.get("/", tags=["root"])
async def root():
    return {
        "service": "Karabuk FWI Wildfire Risk Prediction",
        "architecture": "Option 3 — Stacked (Regression + Safety Classifier)",
        "version": APP_VERSION,
    }
