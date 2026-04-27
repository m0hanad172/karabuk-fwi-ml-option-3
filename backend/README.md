# Backend — Karabük FWI

The Karabük FWI backend is a **FastAPI + SQLite + APScheduler** stack
that fetches weather data, runs the Stacked v3 prediction pipeline,
persists every run into an audit log, and serves the Next.js
dashboard.

## Purpose

- Twice-a-day operational risk prediction (11:00 / 15:00 Europe/Istanbul).
- On-demand manual risk checks via `POST /risk/check`.
- Read-only display of live weather and run history.
- Strictly-isolated YOLOv8 monitoring layer (drone + cameras).

## Folder structure

```
backend/
├── src/                      Application code, imported as `src.*`
│   ├── api/
│   │   ├── main.py           FastAPI lifespan + router wiring
│   │   ├── routes/           risk, weather, history, model, drone, monitoring
│   │   ├── services/         scheduler, history, weather, risk, analytics
│   │   ├── db/               sqlite schema + queries
│   │   ├── time_utils.py     Istanbul-aware ISO 8601 helpers
│   │   ├── run_types.py      Operational vs evaluation taxonomy
│   │   └── json_safe.py      NaN-safe JSON serialization
│   ├── data/                 Open-Meteo + soil-moisture fetchers
│   ├── features/             Feature engineering + schema validators
│   ├── models/                stage1/2 trainers + decision rule
│   ├── inference/            StackedPredictor (production inference)
│   ├── monitoring/           Cameras, drone, YOLO, notifications
│   ├── pipeline/             Training + live inference + drone logic
│   └── evaluation/           Walk-forward + metrics
├── configs/                  paths.py, settings.py — `configs.*`
├── scripts/                  serve.py, train.py, migrations
├── tests/                    Pytest suite (83 tests)
├── models/                   Trained joblib + YOLO weights (committed)
├── data/                     Engineered dataset + OOF predictions + demo notifications
├── outputs/                  Runtime SQLite DB (auto-created, gitignored)
├── requirements.txt
├── pytest.ini
├── .env.example
├── README.md
└── Dockerfile                starter template — see docs/DEPLOYMENT_PLAN.md
```

`src.*` and `configs.*` are imported as **absolute** paths everywhere —
no relative imports inside the package. `pytest.ini` sets
`pythonpath = .` so this layout works whether you run pytest from the
project root or from `backend/`.

## Install dependencies

From the project root:

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

`requirements.txt` pins `scikit-learn==1.6.1` to match the version
that produced the committed joblib artefacts.

## Configure (.env — optional)

Copy the template if you want to override any defaults:

```bash
cp backend/.env.example backend/.env
```

Variables (all optional):

| Variable | Default | Purpose |
|---|---|---|
| `KARABUK_DB_PATH` | `backend/outputs/karabuk_fwi.db` | Override SQLite path |

The backend boots successfully with **zero** environment variables set.

## Run the API

From the project root:

```bash
python backend/scripts/serve.py
```

(`cd backend && python scripts/serve.py` also works.)

- API root: <http://localhost:8000>
- OpenAPI docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/system/health>

## Run tests

From the project root:

```bash
python -m pytest backend/tests -v
```

Or from `backend/`:

```bash
cd backend
python -m pytest -v
```

Test runs use a temp SQLite database via `KARABUK_DB_PATH` (set in
`tests/conftest.py`), so they never pollute the operational DB.

## How models are loaded

`src/inference/predict.StackedPredictor` lazily loads:

- `models/stage1/histgb_regressor.joblib` (HistGradientBoostingRegressor)
- `models/stage2/rf_classifier_stacked.joblib` (RandomForestClassifier)
- `models/metadata/stage2_metadata.json` for the tuned probability threshold

All paths are resolved through `configs/paths.py`, which uses
`Path(__file__).resolve().parent.parent` — so they always anchor to
the `backend/` directory regardless of where the process was started.

The first prediction call after boot is fast: a daemon thread
(`_prewarm_predictor` in `src/api/main.py`) loads both stages during
the FastAPI lifespan startup so the first interactive call doesn't pay
the ~1–2 s cold-load cost.

Per-artefact reference: [`models/README.md`](./models/README.md).

## How SQLite is used

- **Path:** `backend/outputs/karabuk_fwi.db` (auto-created on boot).
- **Tables:** `run_history` (audit log) and `system_state` (key-value
  store for things like the latest drone state).
- **Concurrency:** WAL mode (`PRAGMA journal_mode=WAL`).
- **Override:** `KARABUK_DB_PATH` env var (used by tests).
- **Schema bootstrapping:** `init_db()` in `src/api/db/database.py`
  runs `CREATE TABLE IF NOT EXISTS …` on every boot. There is no
  migration framework — schema changes are additive only. See
  [`../docs/SQLITE_GUIDE.md`](../docs/SQLITE_GUIDE.md).

The detection layer never writes to `run_history` or `system_state` —
that boundary is enforced by code review, not by a constraint.

## Scheduler

APScheduler boots two cron-style jobs in `Europe/Istanbul`:

- `scheduled_morning_run` — daily at **11:00**
- `scheduled_afternoon_run` — daily at **15:00**

Both call `run_operational_check()` from `src/pipeline/live_inference.py`.
Status is exposed at `GET /system/scheduler` and rendered in the
Overview tab. Every `next_run_time` carries an explicit `+03:00` (or
`+04:00` in DST) offset.

## API documentation

OpenAPI / Swagger UI: <http://localhost:8000/docs>
ReDoc: <http://localhost:8000/redoc>

## Architecture invariants

The backend enforces these contracts (see
[`../docs/CORE_IDEA.md`](../docs/CORE_IDEA.md)):

1. The prediction pipeline (`src/features`, `src/inference`,
   `src/pipeline`, `src/api/routes/risk.py`) and the detection layer
   (`src/monitoring/`) do not share any write path into `run_history`
   or `system_state`.
2. Live display weather (`src/api/routes/weather.py`) is never used
   as model input.
3. Every timestamp that crosses the API is produced by
   `src/api/time_utils.py` — tz-aware Istanbul ISO 8601.
4. Only `run_type ∈ { manual, scheduled }` surfaces operationally.
5. Two scheduler slots per day, pinned to Europe/Istanbul.
