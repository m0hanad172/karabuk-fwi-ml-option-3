"""
Service layer for risk check operations.

This layer enforces the operational vs. evaluation separation:

* Only OPERATIONAL runs (manual / scheduled) are allowed to update
  `system_state["latest_drone_state"]` — the value read by `/drone/state`.
* Only OPERATIONAL runs are returned by `get_latest_prediction()` —
  the value read by `/risk/latest` and rendered in the Live Overview card.
* Evaluation runs (test / evaluation) are still persisted to `run_history`
  for audit/analytics, but they can never leak into the live dashboard or
  move the drone policy.
"""
from __future__ import annotations

from src.api.db.database import get_latest_run, save_run, set_system_state
from src.api.run_types import is_operational, normalize_run_type
from src.pipeline.live_inference import run_risk_check


def execute_risk_check(
    target_date: str | None = None,
    run_type: str = "manual",
    allow_drone_trigger: bool = False,
) -> dict:
    """Run a full stacked risk check and persist the result."""
    run_type = normalize_run_type(run_type)

    # The pipeline itself already hard-guards `allow_drone_trigger` to
    # False for non-operational runs, but we re-check here so the service
    # layer is independently safe.
    if not is_operational(run_type):
        allow_drone_trigger = False

    result = run_risk_check(
        target_date=target_date,
        run_type=run_type,
        allow_drone_trigger=allow_drone_trigger,
    )
    save_run(result)

    # Only operational runs may update the live drone policy state.
    if is_operational(result.get("run_type")):
        set_system_state("latest_drone_state", result.get("drone_state", {}))

    return result


def get_latest_prediction() -> dict | None:
    """
    Get the most recent OPERATIONAL prediction.

    Test and evaluation runs are deliberately excluded — they must never
    appear as the live Latest Model Result on the dashboard.
    """
    return get_latest_run(operational_only=True)
