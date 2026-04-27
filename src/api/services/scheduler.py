"""
Scheduler service for automatic risk checks.

Runs at configured hours (default 11:00 and 15:00 Istanbul time). Both
jobs are OPERATIONAL — they use run_type="scheduled" and are allowed to
trigger the drone policy.

The two-run-a-day design (morning + afternoon) is the operational contract
exposed on the dashboard. Both jobs are always registered so the Live
Overview / Scheduler card can always show them.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from configs.settings import SCHEDULED_RUN_HOURS
from src.api.run_types import RUN_TYPE_SCHEDULED
from src.api.services.risk_service import execute_risk_check
from src.api.time_utils import ISTANBUL_TZ

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _scheduled_run(hour: int, slot: str):
    """Execute a scheduled operational risk check."""
    try:
        logger.info(f"Starting scheduled run slot={slot} hour={hour}")
        result = execute_risk_check(
            run_type=RUN_TYPE_SCHEDULED,
            allow_drone_trigger=True,
        )
        logger.info(
            f"Scheduled run ({slot}) complete: "
            f"predicted_fwi={result['predicted_fwi']:.1f}, "
            f"high_risk_flag={result['high_risk_flag']}"
        )
    except Exception as e:
        logger.error(f"Scheduled run ({slot}) failed: {e}")


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return

    # Pin the scheduler's own default timezone to Istanbul so every job
    # stores and reports times in the operational zone — belt and braces
    # with the explicit CronTrigger timezone below.
    _scheduler = BackgroundScheduler(timezone=ISTANBUL_TZ)

    # Operational contract: two daily runs at SCHEDULED_RUN_HOURS (default 11, 15).
    # Both are always registered so the dashboard always shows both slots.
    slot_names = {0: "morning", 1: "afternoon"}
    for idx, hour in enumerate(SCHEDULED_RUN_HOURS[:2]):
        slot = slot_names.get(idx, f"slot{idx}")
        _scheduler.add_job(
            _scheduled_run,
            CronTrigger(hour=hour, minute=0, timezone=ISTANBUL_TZ),
            args=[hour, slot],
            id=f"scheduled_{slot}_run",
            name=f"Scheduled {slot} run ({hour:02d}:00)",
            replace_existing=True,
        )

    _scheduler.start()
    logger.info(
        f"Scheduler started with {len(SCHEDULED_RUN_HOURS[:2])} operational slots: "
        f"{SCHEDULED_RUN_HOURS[:2]}"
    )


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    if _scheduler is None:
        return {"running": False, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        # APScheduler returns a tz-aware datetime when the scheduler's
        # timezone is set. .isoformat() emits a strict ISO 8601 string
        # with an explicit offset (e.g. "2026-04-15T11:00:00+03:00"), which
        # the frontend's `new Date(...)` parses unambiguously.
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run.isoformat() if next_run else None,
            }
        )
    return {"running": _scheduler.running, "jobs": jobs}
