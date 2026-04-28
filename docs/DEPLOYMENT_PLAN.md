# Deployment Plan

This document is the roadmap for taking the Karabük FWI Stacked v3
system from "runs locally" to "runs in containers / runs on a
server". The repo ships **starter Docker templates** so the structure
is in place; this document tracks what is safe to do **now** vs
**later**.

> The Dockerfiles and `docker-compose.yml` have been locally verified
> with `docker compose build`, `docker compose up -d`, backend health,
> frontend startup, manual FWI run, demo Detection Alert, remote smoke
> check, and `docker compose restart` persistence. CI validates compose
> syntax; full image builds stay local/deployment because
> torch/ultralytics are large.

## Phase 0 — current state

- ✅ Backend boots via `python backend/scripts/serve.py`.
- ✅ Frontend boots via `cd frontend && npm run dev`.
- ✅ All trained models are committed (~8 MB total).
- ✅ SQLite database is created automatically on first boot.
- ✅ No paid API keys required (Open-Meteo is public).
- ✅ 97 backend tests passing.
- ✅ GitHub Actions CI for backend tests, smoke check, frontend build,
  and compose config.

## Phase 1 — local Docker (do this first when you start)

Use `docker-compose.yml` at the repo root:

```bash
docker compose up --build
# Backend  → http://localhost:8000
# Frontend → http://localhost:3000
```

What to validate:

1. **Backend image builds.** `docker compose build backend`.
2. **Backend boots inside the container.** `docker compose up backend`
   then `curl http://localhost:8000/system/health`. Both stages should
   load and the SQLite DB should appear under the `backend_outputs`
   volume.
3. **Frontend image builds.** `docker compose build frontend`.
4. **Frontend talks to backend from the browser.** The compose file
   builds the frontend with `NEXT_PUBLIC_API_URL=http://localhost:8000`
   because dashboard requests originate in the user's browser, not
   from the frontend container.
5. **SQLite persistence survives a container restart.**
   `docker compose restart` — your `run_history` rows should still be
   there. Use `docker compose down` to stop the stack, but avoid
   `docker compose down -v` unless you deliberately want to delete the
   runtime volumes.

If any of those fail, fix the Dockerfile rather than working around
it in shell.

## Phase 2 — single-host production

Same compose file, but:

- Pin image tags (`python:3.11-slim` → `python:3.11.9-slim-bookworm`,
  `node:20-alpine` → `node:20.19.0-alpine`) so rebuilds are
  reproducible.
- Mount the `backend/outputs/` volume to a host path you back up
  (e.g. `/srv/karabuk/outputs:/app/outputs`).
- Run behind a reverse proxy (nginx / Caddy / Traefik) with TLS.
- Set `CORS_ORIGINS` to the real frontend origin(s). Production-like
  modes never default to wildcard.
- Set `DEMO_ALERTS_ENABLED=false` unless this is a trusted demo stack.
- Set explicit `restart: unless-stopped` on both services.

## Phase 3 — multi-host or managed deployment (later)

Two things stop being trivial:

1. **SQLite + multiple replicas.** SQLite assumes a single writer.
   If you scale to >1 backend replica, switch to PostgreSQL (the
   schema is small — three tables — and the queries don't use any
   SQLite-specific features beyond `INSERT OR REPLACE`).
2. **Camera + drone hardware.** The monitoring layer expects
   `/dev/video*` (Linux) or DSHOW indices (Windows). You can either
   run the monitoring layer on the host with `--device /dev/video0:
   /dev/video0`, or split it out into a separate "edge" service
   that POSTs detection events to the API. On Docker Desktop for
   Windows, local webcam passthrough to a Linux container is not a
   reliable default; keep live camera demos on the host backend unless
   you deliberately configure and test device passthrough.

## Environment variables

The system needs **almost no config**. The important variables are:

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `BACKEND_ENV` | backend | `development` locally, `production` in Docker | Controls reload defaults and production-like feature defaults |
| `CORS_ORIGINS` | backend | `http://localhost:3000,http://127.0.0.1:3000` | FastAPI CORS allow-list |
| `DEMO_ALERTS_ENABLED` | backend | `true` outside production, `false` in production unless explicitly set | Gates `POST /monitoring/alerts/test` and the frontend Test alert button |
| `KARABUK_DB_PATH` | backend | `backend/outputs/karabuk_fwi.db` | Override SQLite path |
| `NEXT_PUBLIC_API_URL` | frontend (build-time) | `http://localhost:8000` | Backend base URL |

In Docker:

- `NEXT_PUBLIC_API_URL` is a **build-time** variable for Next.js, so
  it must be set when you `docker build` the frontend (the compose
  file does this via `args:`).
- `KARABUK_DB_PATH` should point inside the mounted volume.
- `GET /system/config` exposes only safe public values:
  `backend_env`, `service_mode`, `demo_alerts_enabled`, and `version`.

## Volumes / persistence

| Path inside container | Mount | What it stores |
|---|---|---|
| `/app/outputs/` | named volume `backend_outputs` | SQLite DB, generated reports |
| `/app/data/notifications/` | named volume `backend_notifications` | Detection alerts JSONL + snapshots |

Everything in `backend/models/` and `backend/data/processed/` is
copied into the image at build time — no volume needed. Runtime
notification JSONL/JPG files are excluded by `backend/.dockerignore`
and must not be baked into images.

## Model files in Docker

Models are baked into the backend image (~8 MB total). On retrain,
the regenerated joblib files land back in `backend/models/`, and the
next `docker compose build backend` picks them up.

If a future retraining produces materially larger artefacts (>50 MB),
either:

- introduce **Git LFS** and add a `.gitattributes` file, or
- pull the model from object storage at container start (add an
  `entrypoint.sh` that fetches from S3 / GCS / Azure Blob before
  exec-ing uvicorn).

## Decisions: what to do now vs later

### Do now

- ✅ Ship the starter Dockerfiles + compose file (already in the repo).
- ✅ Document the env var contract (this file).
- ✅ Keep the SQLite path overridable via `KARABUK_DB_PATH`.
- ✅ Verify local Docker build/run/restart behavior.
- ✅ Add CI for backend/frontend checks and compose config.

### Do soon

- Pin Python and Node base images to specific patch versions.
- Split Docker dependencies into a CPU-friendly backend image profile
  so torch/ultralytics do not pull CUDA packages in vanilla Docker.
- Add reverse proxy/TLS and production logging.

### Defer

- Postgres migration. Only worth doing if you need >1 backend replica
  or you outgrow SQLite (unlikely for a per-run audit log).
- Kubernetes / Helm. Overkill for the current footprint.
- Git LFS. Not needed at the current model size.
- Hardware passthrough for monitoring. Easier to keep monitoring on
  the host (or on a dedicated edge box) and have the cloud backend
  receive detection events via webhook.

## Pre-flight checklist (when you do go live)

- [ ] Set `CORS_ORIGINS` to the real frontend origin.
- [ ] Confirm `DEMO_ALERTS_ENABLED=false` unless explicitly demoing.
- [ ] Confirm backend starts with `BACKEND_ENV=production` and no
      Uvicorn reload.
- [ ] Bind to `0.0.0.0` only behind a reverse proxy.
- [ ] Schedule a backup of the `backend_outputs` volume.
- [ ] Confirm Open-Meteo egress from production network.
- [ ] Run `python backend/scripts/migrate_run_timestamps_to_istanbul.py`
      one last time if you are migrating an existing DB.
