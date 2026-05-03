# Deployment Plan

The current prototype runs locally so the backend can access local
camera/video inputs, while remaining drone-ready for a future camera stream.
See [`README.md`](../README.md) for the day-to-day commands.

This document is the deferred container / cloud roadmap — written
once, kept short, and revisited only if the project's hardware
constraints change.

## Why Docker is not the active path

The dashboard's monitoring layer is a primary objective:

- live webcam capture via OpenCV / Windows DSHOW;
- live PC camera capture via the same path;
- live Tello drone control via `djitellopy` (UDP);
- YOLOv8 fire detection on those streams; and
- snapshot evidence persisted alongside the audit log.

Docker Desktop on Windows runs containers in a Linux VM that does
**not** have direct access to host DirectShow devices. Passing the
USB webcam through requires either WSL2-specific tooling (limited),
USBIPD-WIN one-off mounts, or running the Linux Docker engine on a
Linux host with `--device /dev/video0:/dev/video0`. None of these
match the day-to-day demo workflow we want for this project.

For that reason the project ships **no Dockerfiles, no
`docker-compose.yml`, and no Docker step in CI.** Every active
runtime command in the README and `docs/INSTALLATION.md` is direct:
`python backend/scripts/serve.py`, `npm run dev`, the smoke check,
the cleanup script.

## Phase 0 — current state (always supported)

- ✅ `python backend/scripts/serve.py` runs the API on
      <http://localhost:8000>.
- ✅ `npm run dev` runs the dashboard on <http://localhost:3000>.
- ✅ All trained models are committed (~8 MB).
- ✅ SQLite schema (`run_history`, `system_state`, `detection_alerts`)
      is bootstrapped automatically on first boot. Legacy
      `alerts.jsonl` is imported idempotently into
      `detection_alerts` so no historical alert is lost.
- ✅ 108 backend tests passing; smoke check covers every endpoint
      the frontend uses.
- ✅ GitHub Actions runs pytest, smoke check, and the frontend
      production build on every push and PR — no Docker step.

## Phase 1 (deferred) — containerise without monitoring

A Docker stack is only worth shipping when the deployment target
genuinely doesn't need live cameras / drone — e.g. a public,
read-only dashboard fronting a server that someone *else* feeds with
detection events. The shape would be:

- Backend image: `python:3.11-slim`, install backend/requirements
  *minus* `opencv-python`, `ultralytics`, `djitellopy`, copy
  `src/`, `configs/`, `scripts/`, `models/`, `data/`, run uvicorn.
- Frontend image: multi-stage `node:20-alpine`, build with
  `NEXT_PUBLIC_API_URL` baked at build time, serve with `next start`.
- Compose: backend + frontend + named volume for
  `backend/outputs/karabuk_fwi.db`. Snapshots arrive via a webhook
  endpoint (not yet implemented) instead of being captured locally.

Out of scope for the active workflow.

## Phase 2 (deferred) — multi-host

If the project ever scales beyond a single operator console, the
specific things that need attention:

1. **SQLite ↔ Postgres.** SQLite assumes a single writer. Three
   tables (`run_history`, `system_state`, `detection_alerts`) with
   small queries — a Postgres migration is mostly a connector
   change.
2. **Hardware split.** Run the camera / drone capture as a separate
   "edge" service on the operator's laptop, posting detection events
   to the API. The API itself stays portable.
3. **CORS.** Replace the localhost-only allow-list in
   `backend/src/api/main.py` with the real frontend origin and stop
   advertising the demo / test alert endpoint
   (`DEMO_ALERTS_ENABLED=false`).

## What stays unchanged forever

- `backend/configs/paths.py` is the single source of truth for every
  data / model / DB path. All paths are derived from
  `PROJECT_ROOT = Path(__file__).resolve().parent.parent` so the
  backend folder can be relocated without code edits.
- The architectural separation of prediction
  (`run_history` / `system_state`) from monitoring
  (`detection_alerts` + JPG snapshots) — guarded by an AST-level
  test in `backend/tests/test_monitoring.py`.
- The model artefacts and the engineered training set are committed
  to the repo. The `requirements.txt` pin
  (`scikit-learn==1.6.1`) must be respected on any future
  retraining or environment migration.
