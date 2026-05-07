"""
Scheduler service for automatic risk checks.

Runs at configured hours (default 09:00, 11:00, and 15:00 Istanbul time). All
jobs are OPERATIONAL — they use run_type="scheduled" and are allowed to
trigger the drone policy.

The scheduled-check design is the operational contract
exposed on the dashboard. All jobs are always registered so the Live
Overview / Scheduler card can always show them.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from configs.settings import SCHEDULED_RUN_HOURS
from src.api.db.database import get_database_path, get_run_by_id
from src.api.run_types import RUN_TYPE_SCHEDULED
from src.api.services.risk_service import execute_risk_check
from src.api.time_utils import ISTANBUL_TZ

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _timezone_label() -> str:
    return getattr(ISTANBUL_TZ, "key", str(ISTANBUL_TZ))


def _scheduled_run(hour: int, slot: str) -> dict:
    """Execute a scheduled operational risk check."""
    try:
        logger.info(
            "Scheduled risk check triggered slot=%s hour=%02d:00 timezone=%s db=%s",
            slot,
            hour,
            _timezone_label(),
            get_database_path(),
        )
        result = execute_risk_check(
            run_type=RUN_TYPE_SCHEDULED,
            allow_drone_trigger=True,
        )
        logger.info(
            "Scheduled prediction completed slot=%s run_id=%s predicted_fwi=%.1f "
            "high_risk_flag=%s",
            slot,
            result["run_id"],
            result["predicted_fwi"],
            result["high_risk_flag"],
        )
        persisted = get_run_by_id(result["run_id"])
        if persisted is None or persisted.get("run_type") != RUN_TYPE_SCHEDULED:
            raise RuntimeError(
                "scheduled run completed but run_history row was not persisted "
                f"for run_id={result['run_id']}"
            )
        logger.info(
            "Scheduled run_history insert succeeded slot=%s run_id=%s db=%s",
            slot,
            result["run_id"],
            get_database_path(),
        )
        return result
    except Exception as e:
        logger.exception(
            "Scheduled run failed slot=%s hour=%02d:00 timezone=%s db=%s: %s",
            slot,
            hour,
            _timezone_label(),
            get_database_path(),
            e,
        )
        raise


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return

    # Pin the scheduler's own default timezone to Istanbul so every job
    # stores and reports times in the operational zone — belt and braces
    # with the explicit CronTrigger timezone below.
    _scheduler = BackgroundScheduler(timezone=ISTANBUL_TZ)

    # Operational contract: register every configured daily risk-check slot.
    slot_names = {0: "early_morning", 1: "morning", 2: "afternoon"}
    for idx, hour in enumerate(SCHEDULED_RUN_HOURS):
        slot = slot_names.get(idx, f"slot{idx}")
        _scheduler.add_job(
            _scheduled_run,
            CronTrigger(hour=hour, minute=0, timezone=ISTANBUL_TZ),
            args=[hour, slot],
            id=f"scheduled_{slot}_run",
            name=f"Scheduled {slot} run ({hour:02d}:00)",
            replace_existing=True,
            # The default APScheduler misfire grace is 1 second. On a
            # laptop that suspends/resumes (or any host whose scheduler
            # thread blocks past the trigger) every cron slot in the
            # past second is silently skipped — which is the most
            # common reason scheduled rows never appear in run_history
            # while the backend is "running". Ten minutes of grace +
            # coalesce=True catches a delayed slot once and never
            # backfills more than the most-recent missed slot.
            misfire_grace_time=600,
            coalesce=True,
        )
        logger.info(
            "Registered scheduled risk check job id=%s hour=%02d:00 "
            "timezone=%s misfire_grace=600s coalesce=True",
            f"scheduled_{slot}_run",
            hour,
            _timezone_label(),
        )

    _scheduler.start()
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        logger.info(
            "Scheduler boot: job id=%s next_run=%s",
            job.id,
            next_run.isoformat() if next_run else "—",
        )
    logger.info(
        "Scheduler started with %d operational slots: %s timezone=%s db=%s",
        len(SCHEDULED_RUN_HOURS),
        SCHEDULED_RUN_HOURS,
        _timezone_label(),
        get_database_path(),
    )


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    """Snapshot of the operational scheduler.

    Shape:
      ``running``           — bool, whether APScheduler's thread is alive.
      ``timezone``          — string label, e.g. "Europe/Istanbul".
      ``configured_hours``  — list[int] from ``SCHEDULED_RUN_HOURS``.
      ``jobs``              — list of {id, name, next_run_time} entries.

    The extra ``timezone`` and ``configured_hours`` fields are consumed
    by the dashboard's Operational Schedule card and by the
    ``trigger_scheduled_run.py`` diagnostic helper — they make it
    obvious at a glance whether the running scheduler matches the
    configured slots.
    """
    base = {
        "timezone": _timezone_label(),
        "configured_hours": list(SCHEDULED_RUN_HOURS),
    }
    if _scheduler is None:
        return {"running": False, "jobs": [], **base}
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        # APScheduler returns a tz-aware datetime when the scheduler's
        # timezone is set. .isoformat() emits a strict ISO 8601 string
        # with an explicit offset (e.g. "2026-04-15T11:00:00+03:00"),
        # which the frontend's `new Date(...)` parses unambiguously.
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run.isoformat() if next_run else None,
            }
        )
    return {"running": _scheduler.running, "jobs": jobs, **base}
