"""
Canonical run-type taxonomy for the Option 3 prediction pipeline.

There are exactly two classes of runs in the system:

1. OPERATIONAL runs — real, live, field-facing runs.
   - "manual"     : triggered from the dashboard (POST /risk/check)
   - "scheduled"  : triggered by APScheduler at 11:00 / 15:00 Istanbul

   ONLY operational runs:
     * appear in the Live Overview / Latest Model Result card
     * are eligible to trigger the drone policy
     * update /drone/state

2. EVALUATION runs — offline / benchmark / test artifacts.
   - "test"       : seeded by unit tests, ad-hoc probes
   - "evaluation" : holdout benchmarks, model comparison runs

   EVALUATION runs must NEVER:
     * appear as the live latest operational result
     * influence drone trigger logic
     * update /drone/state

This module is the single source of truth for that split. Every place that
reads or writes a run_type MUST go through these constants so the two
classes can never drift apart again.
"""
from __future__ import annotations

# Operational (real, live pipeline)
RUN_TYPE_MANUAL = "manual"
RUN_TYPE_SCHEDULED = "scheduled"

# Evaluation (offline / test / benchmark)
RUN_TYPE_TEST = "test"
RUN_TYPE_EVALUATION = "evaluation"

OPERATIONAL_RUN_TYPES: frozenset[str] = frozenset(
    {RUN_TYPE_MANUAL, RUN_TYPE_SCHEDULED}
)
EVALUATION_RUN_TYPES: frozenset[str] = frozenset(
    {RUN_TYPE_TEST, RUN_TYPE_EVALUATION}
)
ALL_RUN_TYPES: frozenset[str] = OPERATIONAL_RUN_TYPES | EVALUATION_RUN_TYPES


def is_operational(run_type: str | None) -> bool:
    """True iff this run is live/operational and allowed to affect state."""
    return run_type in OPERATIONAL_RUN_TYPES


def is_evaluation(run_type: str | None) -> bool:
    """True iff this run is a test/evaluation artifact (no operational effect)."""
    return run_type in EVALUATION_RUN_TYPES


def normalize_run_type(run_type: str | None) -> str:
    """
    Coerce a run_type into the canonical taxonomy.

    Legacy values like 'scheduled_morning' / 'scheduled_afternoon' collapse
    into 'scheduled'. Unknown values fall back to 'evaluation' so that
    unclassified runs can never accidentally influence the operational
    dashboard or the drone policy.
    """
    if run_type is None:
        return RUN_TYPE_EVALUATION
    rt = run_type.strip().lower()
    if rt.startswith("scheduled"):
        return RUN_TYPE_SCHEDULED
    if rt in ALL_RUN_TYPES:
        return rt
    return RUN_TYPE_EVALUATION
