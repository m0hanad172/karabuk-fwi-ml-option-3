# FireWatch — Karabük FWI Wildfire Risk Prediction

A two-stage machine-learning system that predicts the **Fire Weather
Index (FWI)** for the Karabük region in Turkey and decides, twice a
day, whether tomorrow is a high-risk fire day. It also runs YOLOv8
fire / smoke detection on live camera and Tello-drone feeds.

The official runtime is **Local Hardware Mode**: the backend runs
directly on the host so OpenCV / DSHOW can reach the live USB
webcam and the drone. There is no Docker path in the active
workflow — see [`docs/DEPLOYMENT_PLAN.md`](./docs/DEPLOYMENT_PLAN.md)
for the deferred container roadmap.

---

## What's in the box

```
.
├── backend/                FastAPI + ML + monitoring (Python 3.11)
│   ├── src/                Application code (imported as `src.*`)
│   ├── configs/            paths.py + settings.py (`configs.*`)
│   ├── scripts/            serve.py, train.py, smoke_check.py, …
│   ├── tests/              108 pytest tests
│   ├── models/             Trained joblibs + YOLO weights (~8 MB, committed)
│   ├── data/               Engineered training set + OOF CSVs + camera_mapping
│   ├── outputs/            SQLite DB karabuk_fwi.db (auto-created, gitignored)
│   ├── requirements.txt    sklearn pinned to 1.6.1
│   └── README.md
│
├── frontend/               Next.js 16 + React 19 dashboard
│   ├── src/                App router, components, hooks, lib
│   ├── public/
│   └── README.md
│
├── docs/                   Active operator + reviewer documentation
│   └── archive/            Historical phase notes
│
├── scripts/                PowerShell helpers for Local Hardware Mode
├── legacy_detection_reference/   Reference-only legacy detection prototype
├── README.md               You are here
└── .gitignore
```

---

## System layers

The codebase is organised as six layers. Each one has a single
responsibility and a clear boundary with its neighbours.

| Layer | Where it lives | What it does |
|---|---|---|
| **Data** | `backend/src/data/`, `backend/data/processed/` | Fetches Open-Meteo + soil-moisture, builds the 34 engineered features. |
| **ML prediction** | `backend/src/inference/`, `backend/src/models/`, `backend/models/` | Stage 1 HistGradientBoosting regressor → predicted FWI. Stage 2 RandomForest classifier → high-risk probability. Stacked decision rule applies the 35 / 28 / 0.10 thresholds. |
| **Detection** | `backend/src/monitoring/`, `backend/models/fire_detection/best3.pt` | YOLOv8 fire / smoke detection on webcam, PC camera, and Tello drone feeds. Strictly isolated from the prediction layer. |
| **API / backend** | `backend/src/api/` (FastAPI + APScheduler) | Serves all endpoints, schedules the 11:00 / 15:00 Istanbul runs, prewarms model loads at boot. |
| **Database** | `backend/outputs/karabuk_fwi.db` (SQLite) | Three tables — `run_history` (audit), `system_state` (drone + weather snapshots), `detection_alerts` (read/unread alert log). Snapshots stay as JPGs on disk. |
| **Frontend / dashboard** | `frontend/` | Eight-tab Next.js dashboard. Polls the API; never holds state of its own. |

The **prediction** layer and the **detection** layer never write to
each other's tables. That isolation is enforced by an AST-level test
in `backend/tests/test_monitoring.py`.

---

## Setup

You need **Python 3.11+**, **Node.js 20+**, and **npm 10+**. No paid
API keys: Open-Meteo is free.

```powershell
# from project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

cd frontend
npm install
cd ..
```

Models and the engineered training set are already in the repo, so
you do not need to download anything else.

---

## Run the backend

```powershell
.\.venv\Scripts\Activate.ps1
python backend\scripts\serve.py
```

The API listens on **<http://localhost:8000>**. On boot it:

- creates the SQLite database if it doesn't exist;
- imports any legacy `alerts.jsonl` rows into the `detection_alerts`
  table (idempotent);
- pre-warms the stacked model and the YOLO detector;
- starts APScheduler with two operational slots — 11:00 and 15:00
  Europe/Istanbul.

Useful URLs while the backend is running:

- API docs (Swagger): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/system/health>
- Latest prediction: <http://localhost:8000/risk/latest>

## Run the frontend

```powershell
cd frontend
npm run dev
```

The dashboard listens on **<http://localhost:3000>**.

> **Shortcut.** From the project root, `scripts\start_backend.ps1`
> and `scripts\start_frontend.ps1` do the same as above and also
> auto-create `.venv` / `node_modules` if they're missing.
> `scripts\check_ports.ps1` confirms 8000 and 3000 are free first.

## Run the tests

```powershell
python -m pytest backend\tests -v
```

Current baseline: **108 tests passing**. The test suite uses an
isolated temporary SQLite database so it never touches your real
runtime DB.

A full smoke check (every endpoint the dashboard uses) is one
command:

```powershell
python backend\scripts\smoke_check.py
```

---

## Database

| Item | Location |
|---|---|
| SQLite database | `backend/outputs/karabuk_fwi.db` (auto-created, gitignored) |
| Snapshot JPGs | `backend/data/notifications/<source>_<timestamp>.jpg` |
| Schema doc | [`docs/SQLITE_GUIDE.md`](./docs/SQLITE_GUIDE.md) |

The three tables — `run_history`, `system_state`, `detection_alerts` —
are created on first run. The legacy JSONL evidence file
`backend/data/notifications/alerts.jsonl` is kept on disk but is
no longer written to; on every backend boot, any rows it contains
that are not yet in `detection_alerts` are imported (idempotently).

---

## API endpoints

| Endpoint | Method | What it returns |
|---|---|---|
| `/system/health` | GET | Stage 1 / Stage 2 / DB health |
| `/system/model` | GET | Model metadata + thresholds |
| `/system/scheduler` | GET | APScheduler jobs + next run times |
| `/system/config` | GET | Public runtime flags (env, demo enabled) |
| `/risk/check` | POST | Run a manual FWI check |
| `/risk/latest` | GET | Latest operational prediction |
| `/history/runs` | GET | Paginated run audit log |
| `/history/runs/{id}` | GET | One run with full feature payload |
| `/history/analytics` | GET | Long-range FWI analytics |
| `/weather/live` | GET | Display-only current weather |
| `/drone/state` | GET | Read-only drone launch policy |
| `/monitoring/cameras` | GET | Per-camera status |
| `/monitoring/cameras/{id}/start\|stop` | POST | Start / stop a camera feed |
| `/monitoring/cameras/{id}/feed` | GET | MJPEG stream |
| `/monitoring/drone/start\|stop\|status\|feed` | misc | Tello drone control |
| `/monitoring/alerts` | GET | Detection alerts list (`?source=`, `?filter=unread\|read`) |
| `/monitoring/alerts/summary` | GET | Totals + unread/read counts |
| `/monitoring/alerts/latest` | GET | Newest alert (banner poll target) |
| `/monitoring/alerts/{id}` | GET | One alert with bbox list |
| `/monitoring/alerts/{id}/read\|unread` | POST | Flip read state |
| `/monitoring/alerts/mark-all-read` | POST | Bulk mark read |
| `/monitoring/alerts/test` | POST | Append a synthetic alert (demo mode) |

The full OpenAPI spec is always live at
<http://localhost:8000/docs>.

---

## Dashboard usage

Eight tabs in the sidebar (left → right):

1. **Overview** — current FWI tile, scheduler, live weather.
2. **Impact & Context** — why this matters (Karabük 2025 fires).
3. **Risk Decision** — manual run trigger and decision explanation.
4. **Features** — raw inputs and all 34 engineered features for the
   latest operational run.
5. **Analytics** — long-range FWI trend (yearly / seasonal / monthly).
6. **Run History** — paginated audit log with full drill-down.
7. **Monitoring** — webcam, PC-camera, and drone live feeds; auto-detect.
8. **Detection Alerts** — durable evidence centre with filter pills
   (All / Unread / Read), per-alert mark-as-read, and bulk
   "Mark all as read." The latest alert also surfaces as a banner.

A small **System** tile on the Overview tab shows model info, health,
and the next scheduler run.

All times in the UI are **Europe/Istanbul** (TRT, +03:00 / +04:00).

---

## Troubleshooting

**Dashboard shows nothing.** Run `python backend\scripts\smoke_check.py`.
It checks every endpoint the dashboard uses and prints which one
broke. The most common cause is "fresh clone, no runs yet": click
**Run Manual Check** on the Risk Decision tab.

**Camera says "unavailable".** Run
`python backend\scripts\check_cameras.py` to see which OpenCV
indices are reachable. Then click **Auto-detect** on the Monitoring
tab to bind the highest-resolution opened device to `webcam` and
the next one to `pc_camera`.

**Detection Alerts is empty.** Click **Test alert** in the
Detection Alerts tab — it appends a synthetic fire alert through
the same path as a real detection. If the test alert appears, the
pipeline is wired up correctly; you just don't have any real
detections yet.

**`InconsistentVersionWarning` from joblib.** Your `scikit-learn`
is newer than the pinned 1.6.1. Either downgrade or retrain with
`python backend\scripts\train.py`.

---

## Documentation

- **Where to start:** [`docs/README.md`](./docs/README.md) — index.
- **Architecture:** [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).
- **Run instructions:** [`docs/RUN_PROJECT.md`](./docs/RUN_PROJECT.md).
- **Database schema:** [`docs/SQLITE_GUIDE.md`](./docs/SQLITE_GUIDE.md).
- **Architectural invariants:** [`docs/CORE_IDEA.md`](./docs/CORE_IDEA.md).
- **Goals + phases:** [`docs/PROJECT_BRIEF.md`](./docs/PROJECT_BRIEF.md).
- **Historical phase notes:** [`docs/archive/`](./docs/archive/).

---

## License

Internal academic / research project. Treat as not-for-redistribution
unless the project owners say otherwise.
