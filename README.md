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
│   ├── README.md            Backend-specific docs
│   └── Dockerfile           Starter template (see docs/DEPLOYMENT_PLAN.md)
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
│   ├── README.md
│   └── Dockerfile           Starter template
│
├── docs/                    All long-form project documentation
│   ├── RUN_PROJECT.md       Operator runbook
│   ├── CORE_IDEA.md         Architectural invariants and contracts
│   ├── ARCHITECTURE.md      System architecture deep-dive
│   ├── DEPLOYMENT_PLAN.md   Docker / deployment roadmap
│   ├── SQLITE_GUIDE.md      Schema and migration rules
│   ├── PROJECT_BRIEF.md     Goals and phases
│   ├── PHASE1_SUMMARY.md    Phase 1 — ML core completion notes
│   ├── PHASE3_SUMMARY.md    Phase 3 — frontend foundation notes
│   ├── STATUS.md            Current project status
│   ├── NEXT_STEPS.md        Outstanding follow-ups
│   ├── OLD_PROJECT_NOTES.md Historical notes
│   └── Fire_Prediction_Blueprint.pdf
│
├── docker-compose.yml       Starter template — backend + frontend + volumes
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

## Collaborator quick start

```bash
# 1. Clone
git clone <this-repo-url> karabuk-fwi-ml
cd karabuk-fwi-ml

# 2. (Optional) copy env templates
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# 3. Backend — venv + install
python -m venv .venv
# Windows PowerShell:  .\.venv\Scripts\Activate.ps1
# Linux / macOS:       source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

# 4. Frontend — install
cd frontend && npm install && cd ..

# 5. Run both (two terminals)
# Terminal A — backend (from project root)
python backend/scripts/serve.py
# Terminal B — frontend
cd frontend && npm run dev
```

Then open:

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/system/health>

That is the entire bring-up. **No model files need to be downloaded
separately** — every artefact in `backend/models/` is committed (~8 MB).

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
python -m pytest backend/tests -v
```

Or, equivalently, from inside `backend/`:

```bash
cd backend && python -m pytest -v
```

Both commands work — `backend/pytest.ini` sets the right
`pythonpath` and `testpaths`. Current baseline: **83 tests passing**.
The suite covers prediction, API routes, monitoring, run-type
taxonomy, JSON serialization safety, walk-forward training, and
stacking. Tests redirect the SQLite DB to a temp file, so they never
pollute `backend/outputs/karabuk_fwi.db`.

---

## Docker / deployment

This repository ships **starter templates** for containerised
deployment:

- [`backend/Dockerfile`](./backend/Dockerfile)
- [`frontend/Dockerfile`](./frontend/Dockerfile)
- [`docker-compose.yml`](./docker-compose.yml)

These are conservative, opinionated starting points. They are
**not yet smoke-tested in CI** — treat them as a roadmap. See
[`docs/DEPLOYMENT_PLAN.md`](./docs/DEPLOYMENT_PLAN.md) for the full
deployment checklist (volumes for `backend/outputs/`, env-var
contracts, image build commands, what is safe to do now vs. later).

Quick try (once you have Docker installed):

```bash
docker compose up --build
# Backend at  http://localhost:8000
# Frontend at http://localhost:3000
```

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

**`backend/outputs/karabuk_fwi.db` is missing.**
Created automatically on first backend boot. If the file is locked
on Windows, stop any running backend instance first.

**Wrong timestamps in the dashboard (off by 3 hours).**
Run the one-shot migration:
```bash
python backend/scripts/migrate_run_timestamps_to_istanbul.py
```

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
