"""
Karabuk FWI — backend smoke check.

A fast post-clone / post-deploy sanity probe. Verifies that:

  1. Every model artefact the backend loads at startup is present.
  2. The configured SQLite database is reachable and contains the
     expected tables.
  3. The FastAPI app boots, the scheduler comes up, both stacked
     model stages are loaded, and every endpoint the dashboard
     consumes returns HTTP 200.

Designed to be runnable against either:

  - the local on-disk DB at ``backend/outputs/karabuk_fwi.db``
    (default — uses an in-process FastAPI ``TestClient``), or
  - a separately-running backend over HTTP (pass ``--url
    http://localhost:8000``).

Usage
-----
    # from the project root, hits the backend in-process (fastest):
    python backend/scripts/smoke_check.py

    # or, against an already-running backend on port 8000:
    python backend/scripts/smoke_check.py --url http://localhost:8000

Exit code is 0 if all checks pass, 1 otherwise. Designed so a
collaborator can wire it into a one-line CI step or a git hook.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

# Make `src.*` and `configs.*` importable when running directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The dashboard fetches these endpoints. Keep this list in sync with
# frontend/src/lib/api.ts. Any 5xx or unexpected 4xx → fail.
DASHBOARD_ENDPOINTS = [
    "/",
    "/system/health",
    "/system/model",
    "/system/scheduler",
    "/risk/latest",
    "/history/runs?limit=5&offset=0",
    "/history/analytics",
    "/weather/live",
    "/drone/state",
    "/monitoring/notifications",
    "/monitoring/alerts?limit=5",
    "/monitoring/alerts/summary",
    "/monitoring/alerts/latest",
    "/monitoring/cameras",
    "/monitoring/drone/status",
]


def _check_artefacts() -> list[str]:
    """Return a list of failure messages (empty if every artefact is fine)."""
    from configs.paths import (
        DATASET_PATH,
        FIRE_DETECTION_MODEL_PATH,
        METADATA_DIR,
        STAGE1_DIR,
        STAGE2_DIR,
    )

    failures: list[str] = []
    required = {
        "Stage 1 regressor": STAGE1_DIR / "histgb_regressor.joblib",
        "Stage 2 classifier": STAGE2_DIR / "rf_classifier_stacked.joblib",
        "Stage 1 metadata": METADATA_DIR / "stage1_metadata.json",
        "Stage 2 metadata": METADATA_DIR / "stage2_metadata.json",
        "YOLO weights": FIRE_DETECTION_MODEL_PATH,
        "Processed dataset": DATASET_PATH,
    }
    print("--- artefacts ---")
    for label, path in required.items():
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        flag = "OK" if exists else "MISSING"
        print(f"  [{flag:>7}] {label:<22} {path}  ({size} B)")
        if not exists:
            failures.append(f"missing artefact: {label} -> {path}")
    return failures


def _check_database() -> list[str]:
    """Open the configured SQLite DB and report run-history row count."""
    from src.api.db.database import _db_path  # noqa: SLF001 — internal accessor

    failures: list[str] = []
    db_path = _db_path()
    print("--- database ---")
    print(f"  resolved path : {db_path}")
    if not db_path.exists():
        # Not strictly a failure — the backend creates it on first boot.
        print("  [  WARN ] DB file does not exist yet; will be created on first boot.")
        return failures
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]
        print(f"  tables        : {tables}")
        for required_table in ("run_history", "system_state"):
            if required_table not in tables:
                failures.append(f"DB missing required table: {required_table}")
                print(f"  [   FAIL ] table missing: {required_table}")
        if "run_history" in tables:
            cur.execute("SELECT COUNT(*) FROM run_history")
            n = cur.fetchone()[0]
            print(f"  run_history   : {n} rows")
            if n == 0:
                print(
                    "  [   HINT  ] run_history is empty — the dashboard "
                    "Overview / Run History tabs will look blank until you "
                    "trigger a manual risk check (Risk Decision tab → "
                    "Run Manual Check, or POST /risk/check)."
                )
        if "system_state" in tables:
            cur.execute("SELECT COUNT(*) FROM system_state")
            print(f"  system_state  : {cur.fetchone()[0]} rows")
        conn.close()
    except sqlite3.DatabaseError as e:
        failures.append(f"could not open DB: {e}")
    return failures


def _check_endpoints_in_process() -> list[str]:
    """Boot the FastAPI app via TestClient and probe each endpoint."""
    from fastapi.testclient import TestClient

    from src.api.main import app

    failures: list[str] = []
    print("--- endpoints (in-process) ---")
    with TestClient(app) as c:
        for path in DASHBOARD_ENDPOINTS:
            r = c.get(path)
            ok = r.status_code == 200
            flag = "OK" if ok else "FAIL"
            extra = ""
            if ok:
                j = r.json()
                if isinstance(j, list):
                    extra = f"list[{len(j)}]"
                elif isinstance(j, dict):
                    extra = " ".join(list(j.keys())[:4])
            else:
                extra = r.text[:60]
            print(f"  [{flag:>4}] {r.status_code:>4}  {path:<48} {extra}")
            if not ok:
                failures.append(f"{path} -> {r.status_code}: {r.text[:120]}")
    return failures


def _check_endpoints_remote(base_url: str) -> list[str]:
    """Hit each endpoint over HTTP against an already-running backend."""
    import urllib.request

    failures: list[str] = []
    print(f"--- endpoints ({base_url}) ---")
    for path in DASHBOARD_ENDPOINTS:
        url = base_url.rstrip("/") + path
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                ok = resp.status == 200
                flag = "OK" if ok else "FAIL"
                print(f"  [{flag:>4}] {resp.status:>4}  {path}")
                if not ok:
                    failures.append(f"{path} -> {resp.status}")
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] ERR   {path}  ({e})")
            failures.append(f"{path} -> {e}")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--url",
        help=(
            "If provided, probe this base URL over HTTP (e.g. "
            "http://localhost:8000) instead of booting the app in-process."
        ),
    )
    args = ap.parse_args()

    # Quiet down the FastAPI startup noise so the smoke output is readable.
    logging.disable(logging.WARNING)

    failures: list[str] = []
    failures += _check_artefacts()
    failures += _check_database()
    if args.url:
        failures += _check_endpoints_remote(args.url)
    else:
        failures += _check_endpoints_in_process()

    print()
    if failures:
        print(f"SMOKE CHECK FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SMOKE CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
