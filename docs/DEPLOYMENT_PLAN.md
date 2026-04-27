# Deployment Plan

This document is the roadmap for taking the Karabük FWI Stacked v3
system from "runs locally" to "runs in containers / runs on a
server". The repo ships **starter Docker templates** so the structure
is in place; this document tracks what is safe to do **now** vs
**later**.

> ⚠️ The Dockerfiles and `docker-compose.yml` in this repo are
> conservative starting points and have **not yet been smoke-tested
> end-to-end**. Treat them as a roadmap and validate before relying
> on them in production.

## Phase 0 — current state

- ✅ Backend boots via `python backend/scripts/serve.py`.
- ✅ Frontend boots via `cd frontend && npm run dev`.
- ✅ All trained models are committed (~8 MB total).
- ✅ SQLite database is created automatically on first boot.
- ✅ No paid API keys required (Open-Meteo is public).
- ✅ 83 backend tests passing.

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
4. **Frontend talks to backend over the compose network.** The
   compose file sets `NEXT_PUBLIC_API_URL=http://backend:8000` for
   the frontend container. Open the dashboard and confirm the
   Overview tile populates.
5. **SQLite persistence survives a container restart.**
   `docker compose down && docker compose up` — your `run_history`
   rows should still be there.

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
- Tighten the FastAPI CORS allow-list — currently `["*"]` for dev
  convenience.
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
   that POSTs detection events to the API.

## Environment variables

The system needs **almost no config**. There are only two:

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `KARABUK_DB_PATH` | backend | `backend/outputs/karabuk_fwi.db` | Override SQLite path |
| `NEXT_PUBLIC_API_URL` | frontend (build-time) | `http://localhost:8000` | Backend base URL |

In Docker:

- `NEXT_PUBLIC_API_URL` is a **build-time** variable for Next.js, so
  it must be set when you `docker build` the frontend (the compose
  file does this via `args:`).
- `KARABUK_DB_PATH` should point inside the mounted volume.

## Volumes / persistence

| Path inside container | Mount | What it stores |
|---|---|---|
| `/app/outputs/` | named volume `backend_outputs` | SQLite DB, generated reports |
| `/app/data/notifications/` | named volume `backend_notifications` (optional) | Detection evidence frames |

Everything in `backend/models/` and `backend/data/processed/` is
copied into the image at build time — no volume needed.

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

### Do soon

- Smoke-test `docker compose up --build` on the dev machine — once.
- Pin Python and Node base images to specific patch versions.
- Add a CI job that runs `python -m pytest backend/tests` on every
  push.

### Defer

- Postgres migration. Only worth doing if you need >1 backend replica
  or you outgrow SQLite (unlikely for a per-run audit log).
- Kubernetes / Helm. Overkill for the current footprint.
- Git LFS. Not needed at the current model size.
- Hardware passthrough for monitoring. Easier to keep monitoring on
  the host (or on a dedicated edge box) and have the cloud backend
  receive detection events via webhook.

## Pre-flight checklist (when you do go live)

- [ ] Replace `allow_origins=["*"]` in `backend/src/api/main.py` with
      the real frontend origin.
- [ ] Set `reload=False` in `backend/scripts/serve.py` (it is `True`
      for dev).
- [ ] Bind to `0.0.0.0` only behind a reverse proxy.
- [ ] Schedule a backup of the `backend_outputs` volume.
- [ ] Confirm Open-Meteo egress from production network.
- [ ] Run `python backend/scripts/migrate_run_timestamps_to_istanbul.py`
      one last time if you are migrating an existing DB.
