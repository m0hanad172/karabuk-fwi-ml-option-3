# Karabük FWI Wildfire Risk Prediction — Stacked v3

A two-stage machine-learning system that predicts the **Fire Weather
Index (FWI)** for the Karabük region (Turkey) and decides, twice a day,
whether the next operational day is a high-risk fire day.

The repository contains:

- a **FastAPI** backend with SQLite-backed run history and an
  APScheduler that fires two daily operational runs (11:00 / 15:00
  Europe/Istanbul);
- a **Next.js 16 + React 19** dashboard with eight tabs;
- a fully reproducible training pipeline (HistGradientBoosting +
  RandomForest, stacked) with all trained artefacts checked into the
  repo;
- an isolated **monitoring layer** running YOLOv8 fire detection on
  webcam / PC-camera / Tello drone feeds.

> All operational timestamps are **Europe/Istanbul** (TRT, +03:00).

---

## Table of contents

- [System workflow](#system-workflow)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Collaborator quick start](#collaborator-quick-start)
- [Backend setup](#backend-setup)
- [Frontend setup](#frontend-setup)
- [Database](#database)
- [Model files](#model-files)
- [Environment variables](#environment-variables)
- [Tests](#tests)
- [Runtime data and persistence](#runtime-data-and-persistence)
- [Docker / deployment](#docker--deployment)
- [Common errors and fixes](#common-errors-and-fixes)
- [Documentation index](#documentation-index)

---

## System workflow

```
                Open-Meteo + soil-moisture APIs
                              │
                              ▼
              ┌────────── Feature engineering ──────────┐
              │  backend/src/features/build_features.py │
              │  → 34 engineered features (Group A/B/C) │
              └─────────────────────┬────────────────────┘
                                    ▼
                     Stage 1 — HistGradientBoostingRegressor
                          (backend/models/stage1/*.joblib)
                                    │  predicted_fwi
                                    ▼
                     Stage 2 — RandomForestClassifier
                          (backend/models/stage2/*.joblib)
                          inputs: predicted_fwi + rh + ws + fuel_drying_rate
                                    │  high_risk_probability
                                    ▼
                     Stacked decision rule
                     (backend/src/models/decision.py)
                                    │
                                    ▼
              ┌────────────────────────────────────────────┐
              │  high_risk_flag, decision_reason,          │
              │  drone launch policy, run_history row      │
              └────────────────────────────────────────────┘
                                    │
                                    ▼
                        Next.js dashboard (frontend/)
```

The detection layer (camera + drone + YOLOv8) is **strictly separate**
from this prediction pipeline — it never writes `predicted_fwi` or
`high_risk_flag`.

---

## Project structure

```
project-root/
├── backend/                 FastAPI + ML + monitoring (Python)
│   ├── src/                 Application code, imported as `src.*`
│   │   ├── api/             FastAPI app, routes, services, DB layer
│   │   ├── data/            Open-Meteo / soil-moisture fetchers
│   │   ├── features/        Feature engineering + schema validators
│   │   ├── models/          Stacked decision rule + Stage 1/2 trainers
│   │   ├── inference/       StackedPredictor (production inference)
│   │   ├── monitoring/      Cameras, drone, YOLO detector, notifications
│   │   ├── pipeline/        Training pipeline, live inference, drone logic
│   │   └── evaluation/      Walk-forward + metrics
│   ├── configs/             paths.py, settings.py — imported as `configs.*`
│   ├── scripts/             Entry points (serve, train, migrations)
│   ├── tests/               Pytest suite (83 tests)
│   ├── models/              Trained artefacts (~8 MB total, all committed)
│   │   ├── stage1/          HistGradientBoosting regressor
│   │   ├── stage2/          RandomForest stacked classifier
│   │   ├── metadata/        Per-stage metadata JSON + comparison report
│   │   └── fire_detection/  YOLOv8 weights for monitoring layer
│   ├── data/                Tracked datasets + runtime state
│   │   ├── processed/       Engineered training set
│   │   ├── oof/             Walk-forward OOF predictions
│   │   └── notifications/   Detection evidence (legacy samples kept as demo)
│   ├── outputs/             Runtime SQLite DB (auto-created, gitignored)
│   ├── requirements.txt     Python dependencies (sklearn pinned to 1.6.1)
│   ├── pytest.ini           Test config — pythonpath, testpaths
│   ├── .env.example         Backend env template
│   └── README.md            Backend-specific docs
│
├── frontend/                Next.js 16 + React 19 dashboard
│   ├── src/
│   │   ├── app/             App router
│   │   ├── components/      UI + per-tab pages
│   │   ├── hooks/           use-api hook
│   │   └── lib/             api.ts, i18n, time helpers
│   ├── public/
│   ├── package.json
│   ├── .env.example         Frontend env template
│   └── README.md
│
├── scripts/                 Local Hardware Mode helpers (PowerShell)
│   ├── check_ports.ps1      Confirm 8000 + 3000 are free
│   ├── start_backend.ps1    Boot the API with auto .venv create
│   ├── start_frontend.ps1   Boot the dashboard with auto npm install
│   └── cleanup_local.ps1    Dry-run cleanup for caches / DB backups
│
├── docs/                    All long-form project documentation
│   ├── RUN_PROJECT.md       Operator runbook
│   ├── CORE_IDEA.md         Architectural invariants and contracts
│   ├── ARCHITECTURE.md      System architecture deep-dive
│   ├── DEPLOYMENT_PLAN.md   Deferred container roadmap (not active)
│   ├── SQLITE_GUIDE.md      Schema and migration rules
│   ├── PROJECT_BRIEF.md     Goals and phases
│   ├── PHASE1_SUMMARY.md    ML core completion notes
│   ├── PHASE3_SUMMARY.md    Frontend foundation notes
│   ├── STATUS.md            Current project status
│   ├── NEXT_STEPS.md        Outstanding follow-ups
│   ├── OLD_PROJECT_NOTES.md Historical notes
│   └── Fire_Prediction_Blueprint.pdf
│
├── README.md                You are here
├── .gitignore
└── legacy_detection_reference/   reference-only legacy detection prototype
```

---

## Requirements

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ (3.10 minimum) | sklearn pin requires modern Python |
| Node.js | 20+ | required by Next.js 16 |
| npm | 10+ | ships with Node 20 |
| Git | 2.40+ | |
| OS | Windows 10/11, macOS, Linux | |

The backend additionally needs network access to:

- `api.open-meteo.com`
- `archive-api.open-meteo.com`

No paid API keys are required — Open-Meteo is public and key-less.

---

## Quick start — Local Hardware Mode (official runtime)

The project's official runtime is **Local Hardware Mode**: the
backend runs directly on the Windows host so the dashboard's live
webcam, PC-camera, and Tello drone monitoring can reach the actual
USB devices via DirectShow. This is a core objective of the project,
not a fallback — there is no Docker / cloud path in the active
workflow.

```powershell
# 1. Clone
git clone <this-repo-url> karabuk-fwi-ml
cd karabuk-fwi-ml

# 2. Backend — create venv + install (one-time)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

# 3. Frontend — install (one-time)
cd frontend
npm install
cd ..

# 4. Run both (two terminals from the project root)
# Terminal A — backend on port 8000
.\.venv\Scripts\Activate.ps1
python backend\scripts\serve.py

# Terminal B — frontend on port 3000
cd frontend
npm run dev
```

Or, even shorter, use the wrappers in `scripts\`:

```powershell
powershell -File scripts\check_ports.ps1     # confirms 8000+3000 free
powershell -File scripts\start_backend.ps1   # creates .venv if needed, then serves
powershell -File scripts\start_frontend.ps1  # npm install if needed, then dev
```

Then open:

- Dashboard:    <http://localhost:3000>
- API docs:     <http://localhost:8000/docs>
- Health check: <http://localhost:8000/system/health>

That's the entire bring-up. **No model files need to be downloaded
separately** — every artefact in `backend/models/` is committed
(~8 MB). The first manual run created from the dashboard immediately
shows up in Run History; the first detection raised by the camera or
drone immediately shows up in Detection Alerts.

---

## Backend setup

```bash
python -m pip install -r backend/requirements.txt
python backend/scripts/serve.py
```

Behaviour on boot:

- Initialises the SQLite database at `backend/outputs/karabuk_fwi.db`.
- Pre-warms the stacked predictor (Stage 1 + Stage 2 joblib loads).
- Pre-warms the YOLO detector (best-effort).
- Validates the persisted camera mapping.
- Starts APScheduler with two operational slots: 11:00 and 15:00
  Europe/Istanbul.

Detailed runbook: [`docs/RUN_PROJECT.md`](./docs/RUN_PROJECT.md).
Backend-specific docs: [`backend/README.md`](./backend/README.md).

---

## Frontend setup

```bash
cd frontend
npm install
npm run dev          # development server on http://localhost:3000
npm run build        # production build
npm run start        # production server
npm run lint
```

The frontend reads exactly one environment variable,
`NEXT_PUBLIC_API_URL`, with `http://localhost:8000` as the fallback.
See [`frontend/.env.example`](./frontend/.env.example).

> ⚠️ This project pins **Next.js 16 + React 19**. The conventions
> differ from older Next versions — read
> `frontend/node_modules/next/dist/docs/` (or the official Next 16
> docs) before making framework-level changes.

---

## Database

The backend uses **SQLite** for run history and system state. The
operational database lives at `backend/outputs/karabuk_fwi.db` and is
created automatically on first boot — **no migrations to run, no seed
script to execute, no separate database server**.

- The path is gitignored; collaborators get a fresh DB on their first
  run.
- Override with the `KARABUK_DB_PATH` env var if you need a custom
  location.
- Tests use a temp DB injected via the same env var (see
  `backend/tests/conftest.py`).
- One legacy migration script lives at
  `backend/scripts/migrate_run_timestamps_to_istanbul.py` — only
  needed if you have run-history rows from before the timezone fix.

Schema reference: [`docs/SQLITE_GUIDE.md`](./docs/SQLITE_GUIDE.md).

---

## Model files

Every trained artefact is committed to the repo (~8 MB total), so a
fresh clone is immediately runnable. See
[`backend/models/README.md`](./backend/models/README.md) for the full
breakdown.

| File | Purpose |
|---|---|
| `backend/models/stage1/histgb_regressor.joblib` | Stage 1 FWI regressor |
| `backend/models/stage2/rf_classifier_stacked.joblib` | Stage 2 high-risk classifier |
| `backend/models/metadata/stage1_metadata.json` | Stage 1 metrics |
| `backend/models/metadata/stage2_metadata.json` | Stage 2 metrics + tuned probability threshold |
| `backend/models/metadata/three_way_comparison.json` | Decision-rule comparison shown in the System tab |
| `backend/models/fire_detection/best3.pt` | YOLOv8 fire detector (monitoring layer) |

To retrain:

```bash
python backend/scripts/train.py
```

> `backend/requirements.txt` pins `scikit-learn==1.6.1` to match the
> version used to pickle the joblibs. Do not upgrade sklearn without
> retraining.

**Git LFS is not used.** The total model footprint (~8 MB) is well
under GitHub's 100 MB hard limit. Revisit only if a future retraining
run produces a materially larger artefact.

---

## Environment variables

| Variable | Scope | Default | Purpose |
|---|---|---|---|
| `KARABUK_DB_PATH` | backend | `backend/outputs/karabuk_fwi.db` | Override SQLite location (used by tests). |
| `NEXT_PUBLIC_API_URL` | frontend | `http://localhost:8000` | Backend base URL. |

Templates:
[`backend/.env.example`](./backend/.env.example),
[`frontend/.env.example`](./frontend/.env.example).

No real secrets are required to run the project.

---

## Tests

From the project root:

```bash
python -m pytest backend/tests -q
```

Or, equivalently, from inside `backend/`:

```bash
cd backend && python -m pytest -v
```

Both commands work — `backend/pytest.ini` sets the right
`pythonpath` and `testpaths`. Current baseline: **97 tests passing**.
The suite covers prediction, API routes, monitoring, run-type
taxonomy, JSON serialization safety, walk-forward training, and
stacking. Tests redirect the SQLite DB to a temp file, so they never
pollute `backend/outputs/karabuk_fwi.db`.

### One-shot smoke check

For a quick "is the whole thing wired up correctly?" probe — useful
right after a fresh clone, after pulling new commits, or while
debugging an empty dashboard — run:

```bash
# from project root, in-process (fastest)
python backend/scripts/smoke_check.py

# or, against an already-running backend
python backend/scripts/smoke_check.py --url http://localhost:8000
```

The script verifies every model artefact is on disk, opens the
configured SQLite DB and reports the `run_history` row count, then
hits every endpoint the dashboard consumes. Exit code is 0 on
success and 1 on any failure, so it is safe to chain into a CI
step or a git hook.

GitHub Actions runs the backend pytest suite, the backend smoke
check, and the frontend production build on push and pull request.
Hardware camera / drone paths and Docker are intentionally not run
in CI.

---

## Runtime data and persistence

Two things are durable but **gitignored** (created on first run, never
committed):

- **SQLite database** — `backend/outputs/karabuk_fwi.db`. Holds
  `run_history` (Stacked v3 audit log), `system_state` (drone state,
  live-weather snapshot), and `detection_alerts` (Detection Alerts
  evidence + read/unread state). Schema is bootstrapped automatically
  by `init_db()` on every backend boot.
- **Snapshot JPEGs** — `backend/data/notifications/*.jpg`. Written by
  the YOLO inference loop whenever a detection fires; referenced by
  `detection_alerts.snapshot_path` and served via `/static/notifications/`.

A fresh clone has zero rows in any of these. Trigger a real run from
the dashboard's **Risk Decision** tab to populate `run_history`, or
use the optional demo seeder:

```powershell
.\.venv\Scripts\Activate.ps1
python backend\scripts\seed_demo_runtime.py
```

The seeder appends two synthetic Detection Alerts (one fire, one
smoke, both `source="demo"`) and prints a copy-pasteable curl that
creates a real `run_history` row.

> **Legacy JSONL → SQLite migration is automatic.** If your project
> still has the old `backend/data/notifications/alerts.jsonl` file
> from earlier runs, it is imported into the SQLite
> `detection_alerts` table on the next backend boot. The import is
> idempotent (rows are matched by `alert_id`) and the JSONL file is
> preserved on disk for forensic use.

## Docker / deployment

Docker is **deliberately not part of the active workflow.** The
project's core monitoring objective — live webcam, PC camera, and
Tello drone — depends on Windows DirectShow access that Docker
Desktop on Windows cannot pass through. See
[`docs/DEPLOYMENT_PLAN.md`](./docs/DEPLOYMENT_PLAN.md) for the
deferred container roadmap (when, why, and what would have to change).

Local cleanup is dry-run by default:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cleanup_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\cleanup_local.ps1 -Apply
```

The cleanup helper removes caches and build output only; it never
removes the active SQLite DB, alert JSONL/read-state/JPG evidence,
`.venv`, `node_modules`, or DB backups.

The old `.claude/` worktree folder is not part of the current project
workflow. It is ignored and should be removed locally if it appears;
the active workflow is the normal Git `main` branch plus Codex changes.

---

## Common errors and fixes

**`ModuleNotFoundError: No module named 'src'` when running scripts.**
Run from the project root, or `cd backend` first. The entry-point
scripts inject the right directory into `sys.path` automatically.

**`InconsistentVersionWarning` from joblib.**
You upgraded scikit-learn past 1.6.1. Either downgrade
(`pip install scikit-learn==1.6.1`) or retrain
(`python backend/scripts/train.py`).

**Frontend cannot reach the backend.**
Check that the backend is running on port 8000 and that
`NEXT_PUBLIC_API_URL` either is unset or matches the backend URL.
Restart `npm run dev` after editing `frontend/.env.local`.

**`ultralytics` / OpenCV install fails.**
The monitoring layer is optional. Comment out the `ultralytics`,
`opencv-python` and `djitellopy` lines in `backend/requirements.txt`
if you only need the prediction backend.

**Monitoring camera feed is unavailable.**
The Monitoring tab uses backend OpenCV capture (DSHOW on Windows),
not browser webcam permission prompts. From a fresh clone:

1. Confirm the backend is running locally with
   `python backend\scripts\serve.py` (NOT in Docker — the project's
   official runtime is Local Hardware Mode for exactly this reason).
2. Run the camera diagnostic from the project root:
   `python backend\scripts\check_cameras.py`. It probes the local
   OpenCV indices and reports which ones can deliver a frame.
3. On the Monitoring tab, click **Auto-detect** under Devices
   Detected — the backend rebinds the highest-resolution opened
   index to `webcam` and the next one to `pc_camera`.

Prediction, Run FWI, and Detection Alerts remain fully usable even
when camera hardware is unavailable.

**`backend/outputs/karabuk_fwi.db` is missing.**
Created automatically on first backend boot. If the file is locked
on Windows, stop any running backend instance first.

**Wrong timestamps in the dashboard (off by 3 hours).**
Run the one-shot migration:
```bash
python backend/scripts/migrate_run_timestamps_to_istanbul.py
```

**Detection Alerts tab is empty.** See the
[Detection Alerts and Dashboard Notifications](#detection-alerts-and-dashboard-notifications)
section below — usually means the JSONL evidence log is at a stale
location, or no alerts have been raised yet (click **Test alert** in
the tab header to verify the pipeline is wired up).

**Dashboard is empty (no Overview tile, no Run History rows).**
Almost always one of three things — the smoke check tells you
which:

```bash
python backend/scripts/smoke_check.py
```

1. **Backend is not running**, or the frontend is pointed at the
   wrong URL. Confirm `curl http://localhost:8000/system/health`
   returns `200`, and that `NEXT_PUBLIC_API_URL` in
   `frontend/.env.local` matches.
2. **The SQLite database is empty** — fresh clone, no runs yet.
   Trigger one from the **Risk Decision** tab → **Run Manual
   Check** (or `curl -X POST http://localhost:8000/risk/check
   -H "Content-Type: application/json" -d '{}'`). The new run
   appears in Overview and Run History within a second.
3. **Stale DB at the legacy path** (only if you upgraded across
   the `backend/` restructure). Real history at
   `outputs/karabuk_fwi.db` and an empty new DB at
   `backend/outputs/karabuk_fwi.db`. Migration is a one-liner —
   stop the backend, then:
   ```bash
   # back up the empty DB, copy the legacy one in, archive the
   # legacy file
   mv backend/outputs/karabuk_fwi.db backend/outputs/karabuk_fwi.db.empty.bak
   cp outputs/karabuk_fwi.db backend/outputs/karabuk_fwi.db
   mv outputs/karabuk_fwi.db outputs/karabuk_fwi.db.legacy.bak
   ```
   Both DBs share the same schema, so the data lands in the
   correct tables.

---

## Detection Alerts and Dashboard Notifications

The **Detection Alerts** tab is the durable evidence centre for every
fire / smoke detection raised by the drone, webcam, or PC camera. It
is strictly separate from the FWI prediction pipeline — alerts here
never influence `predicted_fwi`, `high_risk_flag`, or the drone
launch policy.

### Storage

- **SQLite `detection_alerts` table** (`backend/outputs/karabuk_fwi.db`)
  is the source of truth. Holds alert id, Istanbul ISO timestamp,
  label, confidence, source, snapshot path, `is_read` flag,
  `read_at`, severity, and the full per-detection bbox list. The
  schema is bootstrapped by `init_db()` and is byte-compatible with
  the existing `run_history` and `system_state` tables — same DB file,
  separate write paths.
- **JPEG snapshots** stay on disk as
  `backend/data/notifications/<source>_<ts>.jpg`, served via the
  FastAPI static mount at `/static/notifications/`. Referenced by
  `detection_alerts.snapshot_path`.
- **In-memory ring buffer** holds the most recent ~200 alerts for the
  live `/monitoring/notifications` feed. Rehydrated from SQLite at
  startup so a restart never appears to "lose" the live feed.
- **Legacy `alerts.jsonl`** (and the legacy `alerts_read_state.json`
  sidecar) are read once on startup and imported into SQLite by
  `import_legacy_jsonl()`. The import is idempotent (rows match by
  `alert_id`); the JSONL file is preserved on disk for forensic /
  external use, never written to going forward.

The whole `backend/data/notifications/` tree is **gitignored runtime
state** — fresh detections do not dirty the working tree. If you
clone the repo, the directory is created on first detection (the
backend mkdirs it lazily).

### Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /monitoring/alerts` | Paginated list, newest first, optional `?source=drone\|webcam\|pc_camera\|demo` and `?filter=all\|unread\|read` filters. |
| `GET /monitoring/alerts/summary` | `{ total, unread_count, read_count, by_source, max_confidence, last_time_str, last_source, last_by_source }` — drives the summary tiles. |
| `GET /monitoring/alerts/latest` | `{ alert: <single alert> | null }` — cheap poll target for the in-app notification banner. |
| `GET /monitoring/alerts/{alert_id}` | One alert with the full per-detection list (label / confidence / bbox). |
| `POST /monitoring/alerts/{alert_id}/read` | Set `is_read=1, read_at=<istanbul-iso>` for one alert. |
| `POST /monitoring/alerts/{alert_id}/unread` | Set `is_read=0, read_at=NULL` for one alert. |
| `POST /monitoring/alerts/mark-all-read` | Mark every currently logged alert as read. |
| `POST /monitoring/alerts/test?label=fire&confidence=0.78&source=demo` | Append a synthetic alert through the real persistence path when `DEMO_ALERTS_ENABLED=true`. Useful when no camera/drone hardware is available; the frontend hides the **Test alert** button when `/system/config` reports demo alerts disabled. |
| `GET /monitoring/notifications` | Recent ring-buffer view (subset of JSONL). |

### Dashboard notification banner

A floating banner mounted in the app shell
(`frontend/src/components/layout/alert-banner.tsx`) polls
`GET /monitoring/alerts/latest` every 5 seconds. When the latest
alert id changes (i.e. a new fire / smoke detection lands), it shows
a top-right banner with the source, confidence, and snapshot
thumbnail, regardless of which tab the operator has open. The banner
auto-dismisses after 12 seconds and can be closed manually. The
first poll after page load primes the seen-id ref but does NOT
trigger the banner — otherwise every reload would feel like a fresh
detection.

### How to test without camera hardware

1. Open the **Detection Alerts** tab.
2. Click **Test alert** in the header. A synthetic `source="demo"`
   alert appends through the same persistence path as a real
   detection.
3. The summary tiles update, the table gains a row, and the
   floating banner fires (auto-dismisses after 12 s).
4. The alert is durable — refresh the page and it is still there.

Or, from a shell (smoke / CI use):

```bash
curl -X POST "http://localhost:8000/monitoring/alerts/test?label=smoke&confidence=0.91"
```

Demo alerts are tagged with `"source": "demo"` so they can be filtered
or reviewed separately. Treat `alerts.jsonl` as runtime evidence: do
not delete it as part of normal cleanup.

### Hardware unavailable

If the camera / drone hardware isn't plugged in, the Monitoring tab
shows hardware status (camera indices, running/stopped state, drone
status) and the professional unavailable message above. The Detection
Alerts tab shows the existing JSONL evidence (or a clean empty state
with the **Test alert** affordance). Neither tab crashes - every
monitoring import in `backend/src/monitoring/` is optional and degrades
gracefully (see `backend/configs/paths.py::FIRE_DETECTION_MODEL_PATH`
and the ImportError-tolerant import of `cv2` in `notifications.py`).

### Troubleshooting: Detection Alerts is empty

```bash
python backend/scripts/smoke_check.py
```

Look at the `--- endpoints ---` section: if
`/monitoring/alerts/summary` returns `total=0` but you expect rows,
the JSONL evidence log is missing or at a stale path. The most
common cause across the `backend/` restructure: alerts were written
to `data/notifications/alerts.jsonl` (legacy root) and the
post-restructure backend now reads
`backend/data/notifications/alerts.jsonl`. Migrate with:

```bash
mkdir -p backend/data/notifications
mv data/notifications/alerts.jsonl backend/data/notifications/
mv data/notifications/*.jpg        backend/data/notifications/   # if any
```

Restart the backend; `hydrate_ring_buffer_from_log()` picks the new
file up automatically.

---

## Documentation index

| File | Topic |
|---|---|
| [`docs/RUN_PROJECT.md`](./docs/RUN_PROJECT.md) | Operator runbook (boot, scheduler, manual checks, monitoring) |
| [`docs/CORE_IDEA.md`](./docs/CORE_IDEA.md) | Architectural invariants and contracts |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | System architecture deep-dive |
| [`docs/DEPLOYMENT_PLAN.md`](./docs/DEPLOYMENT_PLAN.md) | Docker / deployment roadmap |
| [`docs/SQLITE_GUIDE.md`](./docs/SQLITE_GUIDE.md) | Schema, migrations, conventions |
| [`docs/PROJECT_BRIEF.md`](./docs/PROJECT_BRIEF.md) | Project goals and phases |
| [`docs/PHASE1_SUMMARY.md`](./docs/PHASE1_SUMMARY.md) | ML core completion notes |
| [`docs/PHASE3_SUMMARY.md`](./docs/PHASE3_SUMMARY.md) | Frontend foundation notes |
| [`docs/STATUS.md`](./docs/STATUS.md) | Current project status |
| [`docs/NEXT_STEPS.md`](./docs/NEXT_STEPS.md) | Outstanding follow-ups |
| [`backend/README.md`](./backend/README.md) | Backend-specific docs |
| [`backend/models/README.md`](./backend/models/README.md) | Per-artefact model reference |
| [`backend/data/README.md`](./backend/data/README.md) | Per-folder data reference |
| [`frontend/README.md`](./frontend/README.md) | Frontend-specific docs |

---

## License

Internal academic / research project. Treat as not-for-redistribution
unless the project owners say otherwise.
