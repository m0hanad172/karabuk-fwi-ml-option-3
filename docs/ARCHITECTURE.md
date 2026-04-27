# Architecture

A high-level reference for how the Karabük FWI Stacked v3 system is
put together. Operational invariants and rules-of-the-road live in
[`CORE_IDEA.md`](./CORE_IDEA.md); this document focuses on the
*structure* of the system.

## High-level diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Next.js dashboard                           │
│  Overview · Impact · Risk Decision · Features · Analytics ·          │
│  Run History · Monitoring · System                                   │
└──────────────────────┬───────────────────────────────────────────────┘
                       │  HTTP (NEXT_PUBLIC_API_URL)
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       FastAPI backend (port 8000)                    │
│                                                                      │
│  Routes:  /risk  /weather  /history  /system  /drone  /monitoring    │
│                                                                      │
│  ┌─────────────────────────┐    ┌────────────────────────────────┐  │
│  │  Prediction pipeline    │    │  Monitoring (detection) layer  │  │
│  │  src/features           │    │  src/monitoring                │  │
│  │  src/inference          │    │   - cameras (OpenCV)           │  │
│  │  src/pipeline           │    │   - drone (djitellopy)         │  │
│  │  src/models/decision    │    │   - YOLO detector              │  │
│  │  src/api/routes/risk    │    │   - notifications ring buffer  │  │
│  └────────────┬────────────┘    └───────────────┬────────────────┘  │
│               │ writes                          │ writes             │
│               ▼                                 ▼                     │
│  ┌─────────────────────────┐    ┌────────────────────────────────┐  │
│  │   SQLite                │    │   data/notifications/          │  │
│  │   - run_history         │    │   - alerts.jsonl               │  │
│  │   - system_state        │    │   - <ts>.jpg evidence frames   │  │
│  └─────────────────────────┘    └────────────────────────────────┘  │
│                                                                      │
│  APScheduler — Europe/Istanbul                                       │
│   - 11:00 scheduled_morning_run  ┐                                   │
│   - 15:00 scheduled_afternoon_run│ → run_operational_check()         │
└──────────────────────────────────┼───────────────────────────────────┘
                                   │
                                   ▼
                       Open-Meteo + soil-moisture APIs
```

## The two-stage stacked model

```
34 engineered features (Group A/B/C, see src/features/feature_schema.py)
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Stage 1                                 │
│  HistGradientBoostingRegressor          │
│  models/stage1/histgb_regressor.joblib  │
│  → predicted_fwi (continuous)            │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Stage 2                                 │
│  RandomForestClassifier                 │
│  models/stage2/rf_classifier_stacked.   │
│         joblib                           │
│  inputs:                                 │
│    [predicted_fwi, rh, ws, fuel_drying] │
│  → high_risk_probability ∈ [0, 1]        │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Stacked decision rule                   │
│  src/models/decision.stacked_decision    │
│                                          │
│  IF predicted_fwi >= 35  → HIGH RISK     │
│  ELSE IF predicted_fwi >= 28 AND         │
│       prob >= 0.10        → HIGH RISK    │
│              (grey-zone rescue)          │
│  ELSE                     → not high     │
└──────────────────┬──────────────────────┘
                   │
                   ▼
        high_risk_flag, decision_reason, drone_state
```

Thresholds live in `backend/configs/settings.py`:
`CLASS_THRESHOLD = 35`, `NEAR_THRESHOLD = 28`,
`DEFAULT_PROBABILITY_THRESHOLD = 0.10`.

The Stage 2 probability threshold is overridden at load time by the
value persisted in `models/metadata/stage2_metadata.json` (currently
`0.10` — the same as the default).

## Why the boundary between prediction and monitoring is strict

The prediction pipeline must remain reproducible from the dataset
alone. The monitoring layer depends on hardware (USB cameras, the
Tello drone) that is not available in CI, in tests, or on a fresh
clone. Mixing the two would mean every prediction unit-test has to
mock out OpenCV / YOLO / djitellopy.

Concretely:

- The detection layer **never** writes `predicted_fwi`,
  `high_risk_probability`, or `high_risk_flag`.
- The detection layer **never** writes a row into `run_history` or
  `system_state` (it writes to its own ring buffer + JSONL log).
- The prediction layer **never** reads the detection ring buffer.
- The drone-launch policy is computed from the **latest operational
  prediction**, not from anything the detection layer produces.

## Run-type taxonomy

`src/api/run_types.py` defines five `run_type` values:

- `scheduled` — written by APScheduler at 11:00 / 15:00.
- `manual` — written by `POST /risk/check`.
- `evaluation` — written by walk-forward evaluation; never surfaces
  operationally.
- `test` — written by tests; never surfaces operationally.
- `legacy_*` — pre-fix rows preserved for the audit log.

The Overview card, the Risk Decision tab's "latest" view, and the
drone policy strip all filter to the *operational* run types
(`scheduled`, `manual`).

## Data flow per operational run

```
run_operational_check()      [src/pipeline/live_inference.py]
        │
        ├─ fetch_model_input_for_date()    Open-Meteo + soil-moisture
        ├─ build_history_window()          last N days for derived features
        ├─ build_feature_row_from_raw_inputs()
        ├─ validate_feature_row()          missing / NaN check
        ├─ predict_from_features()         StackedPredictor
        ├─ compute_drone_state()
        └─ save_run()                      INSERT INTO run_history
```

Every step that emits a timestamp routes through
`src/api/time_utils.istanbul_now_iso()` so the audit log is always
TZ-aware.

## Frontend data flow

The frontend is a thin renderer — it has no second source of truth.
Every dashboard tile fetches its own data from the backend:

| Tab | Endpoint(s) |
|---|---|
| Overview | `/risk/latest`, `/system/scheduler`, `/system/health`, `/weather/live` |
| Impact & Context | (static markdown / images) |
| Risk Decision | `/risk/latest`, `/risk/check` (POST) |
| Features | `/risk/latest` (full audit payload) |
| Analytics | `/history` |
| Run History | `/history`, `/history/{run_id}` |
| Monitoring | `/monitoring/...`, `/drone/state` |
| System | `/system/model`, `/system/health`, `/system/scheduler` |

All polling is done by the `useApi` hook in
`frontend/src/hooks/use-api.ts`, which is timezone-naive — it just
forwards the backend's TZ-aware ISO strings. The
`Europe/Istanbul`-aware rendering happens at the leaf component level
via `frontend/src/lib/time.ts`.

## Why the backend is at `backend/` (post-restructure)

Earlier in the project, `src/`, `configs/`, etc. lived at the repo
root. The folder restructure moves them into `backend/` so the top
level cleanly separates *backend* / *frontend* / *docs* / *deployment*
artefacts.

This was safe because every Python entry point — `scripts/serve.py`,
`scripts/train.py`, the pytest `conftest.py`, the migration script —
computes its sys.path anchor as
`Path(__file__).resolve().parent.parent`. After the move, that
expression resolves to `backend/`, which is the new Python project
root containing `src/`, `configs/`, `models/`, `data/`. No import
strings needed to change.

`backend/pytest.ini` sets `pythonpath = .` so `python -m pytest
backend/tests` from the repo root works without a sys.path hack.
