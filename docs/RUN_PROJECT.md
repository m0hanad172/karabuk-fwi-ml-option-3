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
│   ├── pytest.ini
│   └── Dockerfile           (starter template — see docs/DEPLOYMENT_PLAN.md)
├── frontend/                Next.js 16 + React 19 dashboard
├── docs/                    All project documentation (you are here)
├── docker-compose.yml       (starter template)
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

**Docker note:** Docker Desktop on Windows usually cannot see the
physical webcam without device passthrough. Docker remains the preferred
path for prediction, dashboard, Run FWI, and Detection Alerts demos; use
the local host backend when the demo specifically needs live camera
hardware. When the camera is unavailable, the Monitoring tab should stay
usable and show a camera-unavailable message instead of a broken stream.

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
| `/monitoring/alerts` | GET | Durable detection alerts list (Detection Alerts tab) |
| `/monitoring/alerts/summary` | GET | Totals + by-source counts (Detection Alerts summary tiles) |
| `/monitoring/alerts/latest` | GET | Most recent alert — cheap poll for the in-app banner |
| `/monitoring/alerts/{id}` | GET | Single alert with bboxes (detail drawer) |
| `/monitoring/alerts/test` | POST | Append a synthetic alert (demo / smoke-test) |
| `/monitoring/.../feed` | misc | MJPEG streams |

## 9A. Docker quick start

```bash
docker compose build
docker compose up -d
docker compose ps
```

- Backend: <http://localhost:8000>
- Frontend: <http://localhost:3000>
- Health: <http://localhost:8000/system/health>
- Public config: <http://localhost:8000/system/config>

Useful maintenance commands:

```bash
docker compose logs backend --tail=200
docker compose logs frontend --tail=200
docker compose restart
docker compose down
```

Do not run `docker compose down -v` unless you deliberately want to
delete the named volumes. `backend_outputs` stores the Docker SQLite DB
and `backend_notifications` stores Docker alert JSONL/JPG evidence.

The compose backend runs production-like (`BACKEND_ENV=production`, no
Uvicorn reload) and explicitly enables demo alerts for local demo
verification. Set `DEMO_ALERTS_ENABLED=false` for non-demo production.

Camera/drone hardware is local-only unless you configure Docker device
passthrough. Without devices, the monitoring/detection APIs and tabs
still respond and should not crash.

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

Cleanup is dry-run by default:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cleanup_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\cleanup_local.ps1 -Apply
```

It removes caches/build output only and protects the active SQLite DB,
Detection Alerts JSONL/JPGs, `.venv`, `node_modules`, and DB backups.
The old `.claude/` worktree directory is ignored and should be removed
locally if it reappears; it is not part of the current Codex/main branch
workflow.

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
