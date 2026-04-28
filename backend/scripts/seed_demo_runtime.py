"""
Seed a *minimal* set of demo runtime artefacts so a freshly-cloned
collaborator does not see a completely empty dashboard.

Why this exists
---------------
Two things in the project are durable but **gitignored**:

  - ``backend/outputs/karabuk_fwi.db``           - SQLite run history
  - ``backend/data/notifications/alerts.jsonl``  - detection alerts

A fresh clone therefore boots with empty Run History, empty
Detection Alerts, and the dashboard tabs render their (correct)
empty states. That's the right default for production deployments,
but it makes the project look hollow during a doctor / supervisor
demo. This script seeds enough rows to make the dashboard come
alive without committing private runtime data.

What it seeds
-------------
1. Two synthetic detection alerts (one fire, one smoke) tagged
   ``source="demo"`` so they're trivially filterable. They go
   through the same ``add_demo_alert`` path as the
   ``POST /monitoring/alerts/test`` endpoint, so they persist in
   the JSONL evidence log exactly like real detections.
2. The script does NOT seed ``run_history`` rows directly -
   fabricating predictions would dilute the audit log. Instead it
   prints a copy-pasteable ``curl`` command for ``POST /risk/check``
   so the operator can create a real manual run with one command.

Re-running appends another clearly tagged demo fire/smoke pair and
never overwrites or truncates existing runtime data.

Usage
-----
    # from the project root, with the backend NOT running
    python backend/scripts/seed_demo_runtime.py

    # only seed alerts (default), then print the suggested curl
    python backend/scripts/seed_demo_runtime.py --no-history-hint
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make ``src.*`` and ``configs.*`` importable when invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitoring import notifications as notif


def seed_demo_alerts() -> list[dict]:
    """Append one fire alert + one smoke alert via the real path."""
    fire = notif.add_demo_alert(label="fire", confidence=0.81, source="demo")
    smoke = notif.add_demo_alert(label="smoke", confidence=0.66, source="demo")
    return [fire, smoke]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--no-history-hint",
        action="store_true",
        help="Suppress the trailing 'how to seed Run History' tip.",
    )
    args = ap.parse_args()

    print("Seeding demo Detection Alerts...")
    seeded = seed_demo_alerts()
    for a in seeded:
        print(
            f"  appended id={a['id']} source={a['source']} "
            f"max_confidence={a['max_confidence']:.2f}"
        )

    summary = notif.alerts_summary()
    print(
        f"\nalerts_summary now reports total={summary['total']}  "
        f"by_source={summary['by_source']}"
    )

    if not args.no_history_hint:
        print(
            "\nRun History (run_history table) is intentionally NOT "
            "fabricated by this script - synthetic predictions would "
            "dilute the audit log. To create a real demo row, start "
            "the backend and run:\n\n"
            '    curl -X POST http://localhost:8000/risk/check \\\n'
            '         -H "Content-Type: application/json" \\\n'
            "         -d '{\"allow_drone_trigger\": false}'\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
