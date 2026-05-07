"""Simulate a scheduled risk check without waiting for cron.

Calls the same private function the APScheduler job points at, so the
end-to-end path is exercised exactly as a real 09:00 / 11:00 / 15:00
slot would: fetch weather → build features → predict → save_run with
``run_type="scheduled"`` → update ``system_state.latest_drone_state``.

Usage (from the project root, with the .venv active):

    python backend/scripts/trigger_scheduled_run.py
    python backend/scripts/trigger_scheduled_run.py --hour 11 --slot morning

The script never starts APScheduler. It is purely a diagnostic helper
for confirming that the backend can write a row with
``run_type='scheduled'`` to ``backend/outputs/karabuk_fwi.db``. Print
the latest scheduled row from SQLite afterwards to confirm:

    sqlite3 backend\\outputs\\karabuk_fwi.db ^
        "SELECT run_type, run_timestamp, target_date FROM run_history ^
         WHERE run_type='scheduled' ORDER BY run_timestamp DESC LIMIT 5;"
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make `src.*` and `configs.*` importable when invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from configs.settings import SCHEDULED_RUN_HOURS  # noqa: E402
from src.api.services.scheduler import _scheduled_run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--hour",
        type=int,
        default=SCHEDULED_RUN_HOURS[0] if SCHEDULED_RUN_HOURS else 11,
        help=(
            "Hour to simulate (Europe/Istanbul). Defaults to the first "
            "configured slot."
        ),
    )
    ap.add_argument(
        "--slot",
        default="manual_simulation",
        help="Slot label persisted in the log message (e.g. morning).",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print(
        "Simulating a scheduled risk check directly — APScheduler is "
        "NOT started by this script."
    )
    result = _scheduled_run(hour=args.hour, slot=args.slot)
    print()
    print(f"  run_id          : {result['run_id']}")
    print(f"  run_type        : {result['run_type']}")
    print(f"  run_timestamp   : {result['run_timestamp']}")
    print(f"  target_date     : {result['target_date']}")
    print(f"  predicted_fwi   : {result['predicted_fwi']:.2f}")
    print(
        f"  high_risk_flag  : {result['high_risk_flag']} "
        f"(prob {result['high_risk_probability']:.3f})"
    )
    print()
    print(
        "Confirm the row landed in run_history with the SQL one-liner "
        "in this script's docstring."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
