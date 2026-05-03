# FireWatch: Drone-Ready Wildfire Risk Prediction and Fire/Smoke Detection

FireWatch is a final-year project prototype for wildfire monitoring in the
Karabuk region. It combines weather-based wildfire risk prediction, a
fire/smoke detection module, a FastAPI backend, a React/TypeScript dashboard,
and SQLite persistence for run history and detection alerts.

The system is designed as a drone-ready monitoring platform. In the current
prototype, the fire/smoke detection module operates using a local camera or
video stream. Once a drone is available, its camera stream can be configured as
an input source without changing the core detection and alerting pipeline.

## Main Features

- Wildfire risk prediction from weather and FWI-related inputs.
- Two-stage ML flow: FWI regression, high-risk probability, and decision logic.
- Three scheduled risk checks per day (09:00, 11:00, 15:00 Europe/Istanbul) —
  current code runs the 11:00 and 15:00 slots (see
  [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) for the full
  operational design).
- Manual risk check at any time from the dashboard or `POST /risk/check`.
- Fire/smoke detection (YOLOv8) on CCTV / local camera / future drone input.
- High-Risk Drone Patrol Window with a 30-minute Patrol Cycle (operational
  design; full automation pending real drone hardware).
- FastAPI backend with health, prediction, history, monitoring, and alert APIs.
- React/TypeScript dashboard for prediction results, run history, analytics,
  monitoring, and detection alerts.
- SQLite runtime database for predictions, system state, and alert evidence.
- Drone-ready input design for future camera stream integration.

## Technology Stack

| Area | Technology |
|---|---|
| Backend | Python, FastAPI, APScheduler, SQLite |
| ML | scikit-learn, pandas, NumPy, joblib |
| Detection | OpenCV, Ultralytics YOLO |
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Testing | pytest, ESLint |
| Documentation | Markdown, Mermaid diagrams |

## Project Structure

```text
.
|-- backend/                  FastAPI, ML, detection, database, tests
|-- frontend/                 Next.js dashboard
|-- docs/                     Final documentation and diagrams
|-- docs/archive/             Older notes and superseded docs
|-- legacy_detection_reference/ Reference-only older detection prototype
|-- scripts/                  Local helper scripts
|-- data/                     Root-level data area, ignored when generated
|-- outputs/                  Legacy/root runtime output area, ignored
|-- README.md                 Main collaborator guide
```

## Backend Setup

Requirements: Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

Run the backend:

```powershell
python backend\scripts\serve.py
```

Backend URL: `http://localhost:8000`

Useful API pages:

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/system/health`
- Latest prediction: `http://localhost:8000/risk/latest`

## Frontend Setup

Requirements: Node.js 20+ and npm.

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:3000`

The frontend reads `NEXT_PUBLIC_API_URL`; by default it expects the backend at
`http://localhost:8000`.

## Database

Active runtime database:

```text
backend/outputs/karabuk_fwi.db
```

This database is used for the current demo/report state. It contains:

- `run_history`
- `system_state`
- `detection_alerts`

Zero-byte probe/test databases are not part of the final database. See
[docs/DATABASE.md](./docs/DATABASE.md) and
[docs/database/sqlite_schema_summary.md](./docs/database/sqlite_schema_summary.md).

## Run Tests and Checks

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

Current environment notes are tracked in the final cleanup summary when checks
cannot run because of missing dependencies, locked build files, or local
filesystem permissions.

## Main API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | API root metadata |
| `/system/health` | GET | Backend/model/database health |
| `/system/model` | GET | Model metadata and thresholds |
| `/system/scheduler` | GET | Scheduled job status |
| `/system/config` | GET | Public runtime flags |
| `/risk/check` | POST | Run a manual wildfire risk check |
| `/risk/latest` | GET | Latest operational prediction |
| `/history/runs` | GET | Prediction run history |
| `/history/runs/{run_id}` | GET | Full run details |
| `/history/analytics` | GET | Historical FWI analytics |
| `/weather/live` | GET | Display-only live weather snapshot |
| `/drone/state` | GET | Latest drone-ready policy state |
| `/monitoring/cameras` | GET | Local camera status |
| `/monitoring/alerts` | GET | Detection alert list |
| `/monitoring/alerts/test` | POST | Create a demo alert when enabled |

Full details are in [docs/API_REFERENCE.md](./docs/API_REFERENCE.md).

## Screenshot Placeholders

For the final report and presentation, capture:

- Dashboard main page
- Prediction result
- Detection alerts page
- SQLite tables and sample rows
- API health response
- API prediction response
- Test/terminal results
- System architecture, workflow, ERD, and use case diagrams

## Collaborator Notes

- Do not rename backend modules or frontend routes without checking imports.
- Do not change model artifacts, thresholds, API contracts, or database schema
  unless the change is reviewed first.
- Keep probe DBs, caches, `.tmp`, `.next`, and `node_modules` out of Git.
- Use "drone-ready" in documentation unless actual drone hardware is connected.

## Final-Year Project Note

FireWatch is a working academic prototype, not a production emergency response
system. Its strongest current value is showing a complete software pipeline:
weather/FWI risk prediction, detection input handling, alerts, persistence,
dashboard visualization, and a clear path for future drone camera integration.

## Documentation map

| File | What you'll find |
|---|---|
| [`docs/README.md`](./docs/README.md) | Documentation index. Start here. |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Architecture + final operational logic (3 checks, patrol window, patrol cycle). |
| [`docs/INSTALLATION.md`](./docs/INSTALLATION.md) | Setup commands. |
| [`docs/API_REFERENCE.md`](./docs/API_REFERENCE.md) | Endpoint catalogue. |
| [`docs/DATABASE.md`](./docs/DATABASE.md) | SQLite tables + sample queries. |
| [`docs/REPORT_GUIDE.md`](./docs/REPORT_GUIDE.md) | Final-report scaffolding. |
| [`docs/CHANGELOG.md`](./docs/CHANGELOG.md) | Project history in plain English. |
| [`docs/diagrams/`](./docs/diagrams/) | Mermaid diagrams (architecture, workflow, ERDs, use cases). |
