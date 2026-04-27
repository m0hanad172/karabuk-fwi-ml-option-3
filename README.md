# Karabük FWI Wildfire Risk Prediction — Stacked v3

A two-stage machine-learning system that predicts the **Fire Weather
Index (FWI)** for the Karabük region (Turkey) and decides, twice a day,
whether the next operational day is a high-risk fire day.

The repository contains:

- a **FastAPI** backend with SQLite-backed run history and an
  APScheduler that fires two daily operational runs (11:00 / 15:00
  Europe/Istanbul);
- a **Next.js 16 + React 19** dashboard with eight tabs (Overview,
  Impact & Context, Risk Decision, Features, Analytics, Run History,
  Monitoring, System);
- a fully reproducible training pipeline (HistGradientBoosting +
  RandomForest stacked) with all trained artefacts checked into the
  repo;
- an isolated **monitoring layer** that runs YOLOv8 fire detection on
  webcam / PC-camera / Tello drone feeds.

> **All operational timestamps are Europe/Istanbul (TRT, +03:00).**

---

## Table of contents

- [System workflow](#system-workflow)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [For collaborators — clone to running in 5 steps](#for-collaborators--clone-to-running-in-5-steps)
- [Backend — install, configure, run](#backend--install-configure-run)
- [Frontend — install, configure, run](#frontend--install-configure-run)
- [Model files](#model-files)
- [Environment variables](#environment-variables)
- [Tests](#tests)
- [Common errors and fixes](#common-errors-and-fixes)
- [Documentation index](#documentation-index)

---

## System workflow

```
                Open-Meteo + soil-moisture APIs
                              │
                              ▼
              ┌────────── Feature engineering ──────────┐
              │  src/features/build_features.py         │
              │  → 34 engineered features (Group A/B/C) │
              └─────────────────────┬────────────────────┘
                                    ▼
                     Stage 1 — HistGradientBoostingRegressor
                            (models/stage1/*.joblib)
                                    │  predicted_fwi
                                    ▼
                     Stage 2 — RandomForestClassifier
                          (models/stage2/*.joblib)
                          inputs: predicted_fwi + rh + ws + fuel_drying_rate
                                    │  high_risk_probability
                                    ▼
                     Stacked decision rule
                     (src/models/decision.py)
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
.
├── backend/                Marker folder + docs (see backend/README.md).
│                           The actual backend code lives at the repo root in
│                           src/, configs/, scripts/, tests/, models/, data/.
│                           This is intentional — every Python import is
│                           absolute (`from src.*`, `from configs.*`).
├── frontend/               Next.js 16 dashboard (React 19, Tailwind v4)
│   ├── src/
│   │   ├── app/            App router
│   │   ├── components/     UI + per-tab pages
│   │   ├── hooks/          use-api hook
│   │   └── lib/            api.ts, i18n, time helpers
│   ├── package.json
│   └── .env.example
├── src/                    Backend Python source (imported as `src.*`)
│   ├── api/                FastAPI app, routes, services, DB layer
│   ├── data/               Open-Meteo / soil-moisture fetchers
│   ├── features/           Feature engineering + schema validators
│   ├── models/             Stacked decision rule + Stage 1/2 trainers
│   ├── inference/          StackedPredictor (production inference)
│   ├── monitoring/         Cameras, drone, YOLO detector, notifications
│   ├── pipeline/           Training pipeline, live inference, drone logic
│   └── evaluation/         Walk-forward + metrics
├── configs/                Project-wide settings (paths, thresholds)
├── models/                 Trained artefacts (see models/README.md)
│   ├── stage1/
│   ├── stage2/
│   ├── metadata/
│   └── fire_detection/
├── data/                   Tracked datasets + runtime state (see data/README.md)
│   ├── processed/          Engineered training set
│   ├── oof/                Walk-forward OOF predictions
│   └── notifications/      Detection evidence (legacy samples kept as demo)
├── scripts/                Entry points (serve, train, migrations)
├── tests/                  Pytest suite (77+ tests)
├── legacy_detection_reference/   Reference-only legacy detection prototype
├── requirements.txt        Python dependencies (sklearn pinned to 1.6.1)
├── .env.example            Backend env template
├── RUN_PROJECT.md          Operator runbook
├── CORE_IDEA.md            Architecture invariants and contracts
├── SQLITE_GUIDE.md         Database schema + migration rules
└── PROJECT_BRIEF.md        Project goals and phases
```

---

## Requirements

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | sklearn pin requires 3.10+ |
| Node.js | 20+ | required by Next.js 16 |
| npm | 10+ | ships with Node 20 |
| Git | 2.40+ | |
| OS | Windows 10/11, macOS, Linux | examples below show Windows shell |

The backend additionally needs network access to:

- `api.open-meteo.com`
- `archive-api.open-meteo.com`

---

## For collaborators — clone to running in 5 steps

```bash
# 1. Clone
git clone <this-repo-url> karabuk-fwi-ml
cd karabuk-fwi-ml

# 2. (Optional) copy env templates
cp .env.example .env                              # Linux / macOS / Git Bash
cp frontend/.env.example frontend/.env.local
# On PowerShell:  Copy-Item .env.example .env

# 3. Backend — create venv + install
python -m venv .venv
.\.venv\Scripts\Activate.ps1                      # PowerShell
# source .venv/bin/activate                       # macOS / Linux
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Frontend — install
cd frontend
npm install
cd ..

# 5. Run both (two terminals)
# Terminal A — backend
python scripts/serve.py
# Terminal B — frontend
cd frontend && npm run dev
```

Then open:

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/system/health>

That is the entire bring-up. **No model files need to be downloaded
separately** — every artefact in `models/` is committed to the repo
(~8 MB total).

---

## Backend — install, configure, run

```bash
python -m pip install -r requirements.txt
python scripts/serve.py
```

Behaviour on boot:

- Initialises the SQLite database at `outputs/karabuk_fwi.db`
  (auto-created if absent).
- Pre-warms the stacked predictor (Stage 1 + Stage 2 joblib loads).
- Pre-warms the YOLO detector (best-effort; OK to fail).
- Validates the persisted camera mapping.
- Starts APScheduler with two operational slots: 11:00 and 15:00
  Europe/Istanbul.

Key endpoints (full list at `/docs`):

| Endpoint | Method | Purpose |
|---|---|---|
| `/system/health` | GET | Stage 1/2/DB healthcheck |
| `/system/model` | GET | Model metadata + thresholds |
| `/system/scheduler` | GET | APScheduler status + next runs |
| `/risk/check` | POST | Trigger an operational `manual` run |
| `/risk/latest` | GET | Most recent operational prediction |
| `/history` | GET | Paginated run history |
| `/weather/live` | GET | Display-only current weather |
| `/drone/state` | GET | Read-only drone launch policy |
| `/monitoring/...` | misc | Detection feeds + notifications |

A more detailed runbook lives in [`RUN_PROJECT.md`](./RUN_PROJECT.md).

---

## Frontend — install, configure, run

```bash
cd frontend
npm install
npm run dev          # development server at http://localhost:3000
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

## Model files

Every trained artefact is committed to the repo (~8 MB total), so a
fresh clone is immediately runnable. See
[`models/README.md`](./models/README.md) for the full breakdown — what
each file is, which Python module loads it, and how to retrain.

| File | Purpose |
|---|---|
| `models/stage1/histgb_regressor.joblib` | Stage 1 FWI regressor |
| `models/stage2/rf_classifier_stacked.joblib` | Stage 2 high-risk classifier |
| `models/metadata/stage1_metadata.json` | Stage 1 metrics |
| `models/metadata/stage2_metadata.json` | Stage 2 metrics + tuned probability threshold |
| `models/metadata/three_way_comparison.json` | Decision-rule comparison shown in the System tab |
| `models/fire_detection/best3.pt` | YOLOv8 fire detector (monitoring layer) |

To retrain:

```bash
python scripts/train.py
```

> `requirements.txt` pins `scikit-learn==1.6.1` to match the version
> used to pickle the joblib files. Do not upgrade sklearn without
> retraining.

---

## Environment variables

| Variable | Scope | Default | Purpose |
|---|---|---|---|
| `KARABUK_DB_PATH` | backend | `outputs/karabuk_fwi.db` | Override SQLite location (used by tests). |
| `NEXT_PUBLIC_API_URL` | frontend | `http://localhost:8000` | Backend base URL. |

Templates: [`.env.example`](./.env.example),
[`frontend/.env.example`](./frontend/.env.example).

No real secrets are required to run the project — the Open-Meteo APIs
used here are public and key-less.

---

## Tests

```bash
python -m pytest tests/ -v
```

The suite covers prediction, API routes, monitoring, run-type
taxonomy, and JSON serialization safety. `tests/conftest.py` redirects
the SQLite database to a temporary file via `KARABUK_DB_PATH`, so test
runs never pollute `outputs/karabuk_fwi.db`.

---

## Common errors and fixes

**`ModuleNotFoundError: No module named 'src'` when running scripts.**
Run from the repo root, not from inside `scripts/` or `src/`. The
entry-point scripts inject the repo root into `sys.path` automatically.

**`InconsistentVersionWarning` from joblib.**
You upgraded scikit-learn past 1.6.1. Either downgrade
(`pip install scikit-learn==1.6.1`) or retrain (`python scripts/train.py`).

**Frontend cannot reach the backend.**
Check that the backend is running on port 8000 and that
`NEXT_PUBLIC_API_URL` either is unset or matches the backend URL.
Restart `npm run dev` after editing `frontend/.env.local`.

**`ultralytics` / OpenCV install fails.**
The monitoring layer is optional. The prediction pipeline runs without
it. You can comment out the `ultralytics`, `opencv-python` and
`djitellopy` lines in `requirements.txt` if you only need the
prediction backend.

**`outputs/karabuk_fwi.db` is missing.**
It is created automatically on first backend boot. If the file is
locked on Windows, stop any running backend instance first.

**Wrong timestamps in the dashboard (off by 3 hours).**
Run the one-shot migration:
```bash
python scripts/migrate_run_timestamps_to_istanbul.py
```

---

## Documentation index

| File | Topic |
|---|---|
| [`RUN_PROJECT.md`](./RUN_PROJECT.md) | Operator runbook (boot, scheduler, manual checks, monitoring) |
| [`CORE_IDEA.md`](./CORE_IDEA.md) | Architectural invariants and contracts |
| [`PROJECT_BRIEF.md`](./PROJECT_BRIEF.md) | Project goals and phase plan |
| [`PHASE1_SUMMARY.md`](./PHASE1_SUMMARY.md) | Phase 1 — ML core completion notes |
| [`PHASE3_SUMMARY.md`](./PHASE3_SUMMARY.md) | Phase 3 — frontend foundation notes |
| [`STATUS.md`](./STATUS.md) | Current project status |
| [`NEXT_STEPS.md`](./NEXT_STEPS.md) | Outstanding follow-ups |
| [`SQLITE_GUIDE.md`](./SQLITE_GUIDE.md) | SQLite schema, migrations, conventions |
| [`models/README.md`](./models/README.md) | Per-artefact reference |
| [`data/README.md`](./data/README.md) | Per-folder data reference |
| [`backend/README.md`](./backend/README.md) | Why the backend code lives at the repo root |
| [`frontend/README.md`](./frontend/README.md) | Frontend layout + scripts |

---

## License

Internal academic / research project. Treat as not-for-redistribution
unless the project owners say otherwise.
