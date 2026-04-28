# RUN_PROJECT

Practical, exact steps for running the Karabük FWI **Stacked v3** system
locally after the `backend/` + `docs/` restructure. All operational
times are **Europe/Istanbul** (TRT, +03:00 / +04:00 in DST).

## Repository shape

```
project-root/
├── backend/                 FastAPI + ML + monitoring (Python)
│   ├── src/                 Application code, imported as `src.*`
│   ├── configs/             paths.py, settings.py — imported as `configs.*`
│   ├── scripts/             Entry points (serve.py, train.py, migrations)
│   ├── tests/               Pytest suite
│   ├── models/              Trained joblib + YOLO weights
│   ├── data/                Engineered dataset, OOF predictions, demo notifications
│   ├── outputs/             Runtime SQLite database (auto-created, gitignored)
│   ├── requirements.txt
│   ├── .env.example
│   └── pytest.ini
├── frontend/                Next.js 16 + React 19 dashboard
├── docs/                    All project documentation (you are here)
├── scripts/                 Local Hardware Mode helper PowerShell scripts
├── README.md
├── .gitignore
└── legacy_detection_reference/   reference-only legacy prototype
```

---

## 0. Prerequisites

- Windows 10/11, macOS, or Linux
- Python 3.11+ (3.10 minimum). Any conforming interpreter works — the
  pinned `scikit-learn==1.6.1` does not require a specific build of
  Python beyond the language version.
- Node.js 20+ and npm 10+
- Open network access to `api.open-meteo.com` and
  `archive-api.open-meteo.com`

---

## 1. (Recommended) create and activate a virtualenv

From the project root:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux / Git Bash:
source .venv/bin/activate
```

You should see `(.venv)` in the prompt.

---

## 2. Install dependencies

Backend:

```bash
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

Frontend:

```bash
cd frontend
npm install
cd ..
```

---

## 3. Run the backend

From the **project root**:

```bash
python backend/scripts/serve.py
```

(Or, if you prefer, `cd backend && python scripts/serve.py`.)

- API root: <http://localhost:8000>
- OpenAPI docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/system/health>

The backend boots APScheduler with two Istanbul-time operational slots
(11:00 and 15:00) automatically and creates the SQLite database at
`backend/outputs/karabuk_fwi.db` on first boot.

---

## 4. Run the frontend

In a second terminal:

```bash
cd frontend
npm run dev
```

- Dashboard: <http://localhost:3000>
- Default landing: **Overview**
- Sidebar order: Overview → Impact & Context → Risk Decision → Features
  → Analytics → Run History → Monitoring → Detection Alerts → System Info
  → System Flow

The frontend reads `NEXT_PUBLIC_API_URL` (default
`http://localhost:8000`) from `frontend/.env.local`. See
[`frontend/.env.example`](../frontend/.env.example).

All timestamps in the UI display in **Europe/Istanbul**.

---

## 5. Verify the scheduler

```bash
curl http://localhost:8000/system/scheduler
```

Expected shape:

```json
{
  "running": true,
  "jobs": [
    {
      "id": "scheduled_morning_run",
      "name": "Scheduled morning run (11:00)",
      "next_run_time": "2026-04-28T11:00:00+03:00"
    },
    {
      "id": "scheduled_afternoon_run",
      "name": "Scheduled afternoon run (15:00)",
      "next_run_time": "2026-04-27T15:00:00+03:00"
    }
  ]
}
```

Every `next_run_time` MUST carry an explicit `+03:00` offset (or
`+04:00` during DST). If one is missing, time handling has regressed —
see `backend/src/api/time_utils.py`.

---

## 6. Run a manual risk check

Three ways to trigger a `manual` operational run:

1. **UI:** Risk Decision tab → click **Run Manual Check**.
2. **curl:**
   ```bash
   curl -X POST http://localhost:8000/risk/check \
        -H "Content-Type: application/json" \
        -d '{"allow_drone_trigger": false}'
   ```
3. **Docs playground:** <http://localhost:8000/docs> → `POST /risk/check` → Try it out.

---

## 7. Run the test suite

From the project root:

```bash
python -m pytest backend/tests -q
```

Or from inside `backend/`:

```bash
cd backend
python -m pytest -q
```

Both commands work — `backend/pytest.ini` sets `pythonpath = .` and
`testpaths = tests`. Current baseline: **97 backend tests passing**.

Test runs use an isolated SQLite database via `KARABUK_DB_PATH` set in
`backend/tests/conftest.py`, so they never pollute
`backend/outputs/karabuk_fwi.db`.

---

## 8. Monitoring: camera / drone feeds

The monitoring layer is **strictly separate** from the prediction
pipeline — it never writes `predicted_fwi` or `high_risk_flag`.

**Start/stop feeds from the UI:** Monitoring tab → three feed cards
(Drone, Webcam, PC Camera) with Start/Stop buttons. Streams are MJPEG:

- `GET /monitoring/drone/feed`
- `GET /monitoring/cameras/webcam/feed`
- `GET /monitoring/cameras/pc_camera/feed`

**Drone policy view:** the Monitoring tab's top strip reads
`GET /drone/state`, which is driven by the latest **operational**
prediction — NOT by the detection layer.

**Fire detection notifications:** `GET /monitoring/notifications`
returns the ring buffer (last 200 events). The dashboard polls every
5 seconds. Detection timestamps are always Istanbul-local.

**Camera runtime:** camera capture happens in the FastAPI backend via
OpenCV; the browser only displays the backend MJPEG stream. For a live
webcam demo on Windows, run `python backend/scripts/serve.py` on the
host and use **Devices Detected** / **Auto-detect** to map indices from
`backend/data/camera_mapping.json`.
Use `python backend/scripts/check_cameras.py` for a quick host-side
OpenCV diagnostic.

**Local Hardware Mode is the only official runtime.** Docker is
deliberately not part of the active workflow because Docker Desktop on
Windows cannot pass through the host webcam / Tello drone — and live
monitoring is a core objective of this project. See
[`DEPLOYMENT_PLAN.md`](./DEPLOYMENT_PLAN.md) for the deferred
container roadmap.

---

## 9. Endpoints reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/system/health` | GET | Stage 1/2/DB healthcheck |
| `/system/model` | GET | Model metadata + thresholds |
| `/system/scheduler` | GET | APScheduler status + next runs |
| `/system/config` | GET | Safe public runtime flags (`backend_env`, `service_mode`, `demo_alerts_enabled`, `version`) |
| `/risk/check` | POST | Trigger an operational `manual` run |
| `/risk/latest` | GET | Latest operational prediction |
| `/history/runs` | GET | Paginated run history (used by Run History tab) |
| `/history/runs/{run_id}` | GET | Run detail (validation, features, thresholds) |
| `/history/analytics` | GET | Long-range FWI analytics (used by Analytics tab) |
| `/weather/live` | GET | Display-only current weather snapshot |
| `/drone/state` | GET | Read-only drone launch policy |
| `/monitoring/cameras` | GET | Per-camera status (used by Monitoring tab) |
| `/monitoring/drone/status` | GET | Drone feed status (Monitoring tab) |
| `/monitoring/notifications` | GET | Live ring-buffer of recent detections |
| `/monitoring/runtime` | GET | Runtime hint for camera availability (host OS, in-Docker flag — always `false` in Local Hardware Mode) |
| `/monitoring/alerts` | GET | Durable detection alerts list; supports `filter=all\|unread\|read` |
| `/monitoring/alerts/summary` | GET | Totals, unread/read counts, and by-source counts |
| `/monitoring/alerts/latest` | GET | Most recent alert — cheap poll for the in-app banner |
| `/monitoring/alerts/{id}` | GET | Single alert with bboxes (detail drawer) |
| `/monitoring/alerts/{id}/read` | POST | Mark one detection alert as read |
| `/monitoring/alerts/{id}/unread` | POST | Mark one detection alert unread again |
| `/monitoring/alerts/mark-all-read` | POST | Mark all current detection alerts as read |
| `/monitoring/alerts/test` | POST | Append a synthetic alert (demo / smoke-test) |
| `/monitoring/.../feed` | misc | MJPEG streams |

## 9A. PowerShell helper scripts (Local Hardware Mode)

```powershell
# from project root
powershell -File scripts\check_ports.ps1     # 8000 + 3000 free?
powershell -File scripts\start_backend.ps1   # creates .venv if needed
powershell -File scripts\start_frontend.ps1  # npm install if needed
powershell -File scripts\cleanup_local.ps1   # dry-run; -Apply to delete
```

Camera diagnostic without booting the API:

```powershell
.\.venv\Scripts\Activate.ps1
python backend\scripts\check_cameras.py
```

## 9B. Demo data and cleanup

Fresh clones may start with empty Run History and Detection Alerts
because runtime data is gitignored. To create demo Detection Alerts
without private local data:

```bash
python backend/scripts/seed_demo_runtime.py
```

The script appends one fire and one smoke alert tagged `source="demo"`.
It does not overwrite the active alert log or fabricate `run_history`;
use the UI **Run Manual Check** button or `POST /risk/check` for a real
run-history row.

Detection alert read/unread state lives in the SQLite
`detection_alerts` table (`is_read`, `read_at`). Snapshots stay as
JPG files under `backend/data/notifications/`. None of that is
committed — the SQLite DB and snapshots are gitignored runtime state.
On startup the backend runs a one-time idempotent import of any
legacy `alerts.jsonl` rows into SQLite.

Cleanup is dry-run by default:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cleanup_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\cleanup_local.ps1 -Apply
```

It removes caches/build output only and protects the active SQLite DB,
Detection Alert JPG snapshots and the legacy JSONL, `.venv`,
`node_modules`, and DB backups.

### Operational timing contract

- Morning run: **11:00** Istanbul, `run_type = scheduled`
- Afternoon run: **15:00** Istanbul, `run_type = scheduled`
- Manual runs: on-demand, `run_type = manual`
- Test/evaluation runs: NEVER appear in Overview or drone policy.

---

## 10. Troubleshooting: dashboard shows no data

If the dashboard renders but every tile is empty / "no data", run
the smoke check first:

```bash
python backend/scripts/smoke_check.py
```

It opens the configured SQLite DB, reports the `run_history` row
count, and probes every endpoint the frontend uses. The output
points to one of three causes:

1. **Backend not running, or wrong API URL.** Confirm
   `curl http://localhost:8000/system/health` returns `200`. Check
   `frontend/.env.local` — `NEXT_PUBLIC_API_URL` must point at the
   running backend (default `http://localhost:8000`). Restart
   `npm run dev` after any change to `.env.local`.
2. **`run_history` is empty (0 rows).** Either you have a fresh
   clone or a fresh DB. Trigger a manual run from the **Risk
   Decision** tab → **Run Manual Check** (or
   `POST /risk/check`). The new row shows up immediately in
   Overview and Run History.
3. **Stale legacy DB at the root** (only relevant if you upgraded
   across the `backend/` restructure). The smoke check shows the
   resolved DB path — if your old runs live at
   `outputs/karabuk_fwi.db` but the resolved path is
   `backend/outputs/karabuk_fwi.db`, copy the legacy file in:
   ```bash
   mv backend/outputs/karabuk_fwi.db backend/outputs/karabuk_fwi.db.empty.bak
   cp outputs/karabuk_fwi.db backend/outputs/karabuk_fwi.db
   mv outputs/karabuk_fwi.db outputs/karabuk_fwi.db.legacy.bak
   ```
   The schema is unchanged across the restructure, so the data
   lands in the right tables. Restart the backend to pick up the
   new DB.
