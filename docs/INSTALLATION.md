# Installation

This guide explains how to run FireWatch locally for development, demo, and
final-year project evaluation.

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm
- Windows PowerShell or a compatible terminal

The project does not require a paid weather API key for the current prototype.

## Backend Setup

From the project root:

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

Backend URL:

```text
http://localhost:8000
```

Useful checks:

```powershell
curl http://localhost:8000/system/health
curl http://localhost:8000/system/model
```

## Frontend Setup

From the project root:

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:3000
```

## Scheduled Risk Checks

The operational design runs three scheduled risk checks per day in
**Europe/Istanbul** time:

- 09:00
- 11:00
- 15:00

The current code runs the 09:00, 11:00, and 15:00 slots
(`backend/configs/settings.py::SCHEDULED_RUN_HOURS`). See
[`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full operational logic
(patrol windows, patrol cycle, CCTV vs drone).

## Environment Notes

Backend optional environment file:

```text
backend/.env
```

Use `backend/.env.example` as the template.

Safe drone defaults:

```text
DRONE_MODE=mock
DRONE_AUTO_CONNECT=false
DRONE_VIDEO_ENABLED=true
DRONE_ALLOW_MANUAL_CONTROL=false
DRONE_ALLOW_AUTO_TAKEOFF=false
DRONE_REQUIRE_OPERATOR_CONFIRMATION=true
```

Use `DRONE_MODE=tello` only for an operator-controlled DJI Tello demo.
Starting the stream does not take off. Physical launch requires operator
confirmation and a separate safety check.

Frontend optional environment file:

```text
frontend/.env.local
```

Use `frontend/.env.example` as the template. The main frontend variable is:

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Database Location

Active SQLite database:

```text
backend/outputs/karabuk_fwi.db
```

Do not use zero-byte probe/test databases for the report or demo.

## Running Tests

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Frontend lint:

```powershell
cd frontend
npm run lint
```

Frontend production build:

```powershell
cd frontend
npm run build
```

## Helper Scripts

From the project root:

```powershell
scripts\check_ports.ps1
scripts\start_backend.ps1
scripts\start_frontend.ps1
```

Backend utility scripts:

```powershell
python backend\scripts\smoke_check.py
python backend\scripts\check_cameras.py
python backend\scripts\seed_demo_runtime.py
```

## Common Troubleshooting

### Backend dependency errors

Make sure the `.venv` is active and dependencies were installed from
`backend\requirements.txt`.

### Frontend cannot reach backend

Check that the backend is running on `http://localhost:8000` and that
`NEXT_PUBLIC_API_URL` is correct.

### Camera unavailable

Use:

```powershell
python backend\scripts\check_cameras.py
```

Then use the dashboard monitoring tab or camera API to select the correct local
camera index.

### No prediction history

Run a manual risk check from the dashboard or call:

```powershell
curl -X POST http://localhost:8000/risk/check -H "Content-Type: application/json" -d "{}"
```

### Tests cannot create SQLite temp files

This is usually a local filesystem permission issue involving `.tmp` or
`.pytest_cache`. It does not mean the active runtime database is missing.

### Frontend build cannot remove `.next` files

Stop any running Next.js development server and retry. Locked `.next` files can
prevent production builds on Windows.
