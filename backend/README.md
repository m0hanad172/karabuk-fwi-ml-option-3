# Backend

The Karabük FWI ML backend is the FastAPI + SQLite + APScheduler stack
that fetches weather, runs the Stacked v3 pipeline, persists audit rows,
and serves the dashboard.

## Layout

The backend's source is **not** physically inside this directory — it is
distributed across a handful of top-level folders that every Python
import and every test expects by name:

```
backend/         ← this marker directory + docs (you are here)
src/             ← application code (api / monitoring / features / inference / …)
scripts/         ← entry points (serve.py, train.py, migrate_*.py)
configs/         ← configs/paths.py, configs/settings.py (imported as `configs.*`)
models/          ← trained artefacts: stage1/, stage2/, fire_detection/, metadata/
data/            ← runtime state: sqlite db, notifications, camera mapping
tests/           ← pytest suite
requirements.txt ← Python deps
```

### Why the code isn't inside `backend/`

Moving the folders would break:

- Every absolute import (`from src.api.main …`, `from configs.paths …`).
- `scripts/serve.py`'s `sys.path.insert` wiring.
- Pytest discovery — every test imports `src.*` / `configs.*`.
- Paths baked into `configs/paths.py` (absolute model + data paths).
- Documentation and operator runbooks (`RUN_PROJECT.md`,
  `SQLITE_GUIDE.md`, `CORE_IDEA.md`).

A pure physical rename is a one-shot, codebase-wide refactor — planned
as an optional follow-up, not a hot-path cleanup.

## Entry points

Start the API server:

```powershell
"C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe" scripts/serve.py
# API:  http://localhost:8000
# Docs: http://localhost:8000/docs
```

Run the test suite:

```powershell
"C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe" -m pytest tests/ -v
```

Full runbook in `../RUN_PROJECT.md`.

## Architecture contracts

The backend enforces these invariants (see `../CORE_IDEA.md`):

1. The prediction pipeline (`src/features`, `src/inference`,
   `src/pipeline`, `src/api/routes/risk.py`) and the detection layer
   (`src/monitoring/`) do not share any write path into `run_history` or
   `system_state`.
2. Live display weather (`src/api/routes/weather.py`) is never used as
   model input.
3. Every timestamp that crosses the API is produced by
   `src/api/time_utils.py` — tz-aware Istanbul ISO 8601.
4. Only `run_type ∈ { manual, scheduled }` surfaces operationally.
5. Two scheduler slots per day, pinned to Europe/Istanbul.
