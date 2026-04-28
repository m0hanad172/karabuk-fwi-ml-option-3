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
├── tests/                    Pytest suite (97 tests)
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
| `BACKEND_ENV` | `development` | `development` enables reload by default; `production`/`docker` disables reload and uses production-like feature defaults |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | FastAPI CORS allow-list; production-like modes never default to wildcard |
| `DEMO_ALERTS_ENABLED` | `true` outside production, `false` in production unless explicitly set | Gates `POST /monitoring/alerts/test` and the frontend Test alert button |
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
python -m pytest backend/tests -q
```

Or from `backend/`:

```bash
cd backend
python -m pytest -q
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

## Detection Alerts

Fire / smoke detections raised by the monitoring layer (drone /
webcam / PC camera) are persisted independently of `run_history`:

- **JSONL evidence log:** `data/notifications/alerts.jsonl`
  (append-only, lock-protected).
- **Read-state sidecar:** `data/notifications/alerts_read_state.json`
  stores read alert ids so the evidence log stays append-only.
- **JPEG snapshots:** `data/notifications/<source>_<ts>.jpg`, served
  via the FastAPI static mount at `/static/notifications/`.
- **In-memory ring buffer (200 entries):** rehydrated from the JSONL
  log on every backend boot via
  `notifications.hydrate_ring_buffer_from_log()`, so the live feed
  is never empty after a restart.

Endpoints (full table: see the
[Detection Alerts and Dashboard Notifications](../README.md#detection-alerts-and-dashboard-notifications)
section in the root README):

- `GET /monitoring/alerts` — durable list, newest first.
- `GET /monitoring/alerts/summary` — totals + by-source counts.
- `GET /monitoring/alerts/latest` — single most-recent alert (cheap
  poll target for the in-app banner).
- `GET /monitoring/alerts/{alert_id}` — single alert with bboxes.
- `POST /monitoring/alerts/{alert_id}/read` / `unread` — update
  read state in the sidecar.
- `POST /monitoring/alerts/mark-all-read` — mark every current alert
  as read without rewriting `alerts.jsonl`.
- `POST /monitoring/alerts/test` — append a synthetic alert via the
  real persistence path when `DEMO_ALERTS_ENABLED=true`. Useful for
  end-to-end testing the dashboard when no camera / drone hardware is
  plugged in.

The whole `data/notifications/` tree is gitignored runtime state.
Adding `?source=drone|webcam|pc_camera` to the list endpoint filters
the evidence log; adding `?filter=unread|read` filters by read state.
Demo alerts (`POST /alerts/test`) are tagged `source="demo"` so they
are easy to filter or review separately. Do not delete the alert log or
read-state sidecar as part of normal cleanup.

`GET /system/config` returns the safe public runtime flags consumed by
the frontend: `backend_env`, `service_mode`, `demo_alerts_enabled`, and
`version`. It does not expose local paths or secrets.

Optional demo seeding:

```bash
python backend/scripts/seed_demo_runtime.py
```

This appends one demo fire alert and one demo smoke alert. It does not
overwrite existing runtime data and it does not fabricate Run History;
use `POST /risk/check` or the dashboard **Run Manual Check** button for
a real operational row.

## Monitoring cameras

Camera feeds are backend-driven: OpenCV opens the device, the backend
serves MJPEG at `/monitoring/cameras/{cam_id}/feed`, and the browser
only displays that stream. The Monitoring tab never requests browser
webcam permissions.

On Windows, run the backend directly on the host for a live webcam demo:

```bash
python backend/scripts/serve.py
```

Then use the Monitoring tab's **Devices Detected** strip or
`GET /monitoring/cameras/devices` to confirm the OpenCV indices. Docker
Desktop on Windows does not expose physical webcams to Linux containers
by default; in that runtime the camera cards should remain usable and
show: "Camera is unavailable in this runtime. For webcam monitoring,
run the backend locally or configure Docker device passthrough."

For a host-side diagnosis without starting the API server:

```bash
python backend/scripts/check_cameras.py --max-index 4
```

`GET /monitoring/runtime` returns the same runtime hint consumed by the
frontend (`in_docker`, `host_os`, and `camera_passthrough_supported`).

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
