# SQLITE_GUIDE

Everything you need to know about the operational database that backs the
Karabük FWI Option 3 dashboard.

---

## 1. Where the database lives

- **Production path:** `outputs/karabuk_fwi.db` (relative to the repo root).
- **Test override:** `tests/conftest.py` sets the `KARABUK_DB_PATH`
  environment variable to a temp file, so running `pytest` never writes
  into the production DB.
- **Resolution code:** `src/api/db/database.py::_db_path()`. It checks
  `KARABUK_DB_PATH` first and falls back to `OUTPUTS_DIR / "karabuk_fwi.db"`.
  The path is resolved lazily on every call, so you can point a running
  process at a different file by exporting the env var before the first
  query.

The DB file is created on first use. `get_connection()` also enables
WAL journal mode so concurrent reads from the API never block scheduler
writes.

---

## 2. Why SQLite (and not Postgres)

This is a single-operator local console. The storage needs are modest:

- A few thousand rows of run history per year of operation.
- Two small JSON payloads per row (raw inputs + engineered features).
- A tiny key/value table for system state.

SQLite meets all of it with zero install footprint, zero network config,
and it ships with Python. It is the right choice **only** because the
pipeline writes sequentially (one run at a time, from a single process)
and the API reads are all small point lookups or short range scans.

---

## 3. Schema

Two tables, defined in `src/api/db/database.py::_CREATE_TABLES`.

### 3.1 `run_history`

Every operational, manual, and evaluation run lands here.

| Column | Type | Notes |
|---|---|---|
| `run_id` | TEXT PRIMARY KEY | Short hex id produced by the pipeline |
| `run_type` | TEXT NOT NULL | Canonicalised via `normalize_run_type()` — one of `manual`, `scheduled`, `test`, `evaluation` |
| `run_timestamp` | TEXT NOT NULL | **tz-aware Istanbul ISO 8601** (see `src/api/time_utils.py`) |
| `target_date` | TEXT NOT NULL | Istanbul-local `YYYY-MM-DD` the run is predicting for |
| `predicted_fwi` | REAL | Stage 1 regression output |
| `high_risk_probability` | REAL | Stage 2 classifier probability |
| `high_risk_flag` | INTEGER | 0 / 1 final decision |
| `decision_reason` | TEXT | Human-readable reason ("Stage 1 above threshold", "Stage 2 rescue in grey zone", "Below risk zone") |
| `drone_triggered` | INTEGER | 0 / 1 — derived from `drone_state.active_alert_window` |
| `raw_inputs_json` | TEXT | JSON blob: raw Open-Meteo inputs used by this run |
| `feature_values_json` | TEXT | JSON blob: all 34 engineered feature values |
| `validation_json` | TEXT | JSON blob: `is_valid`, `missing_features`, `nan_features`, `checked` |
| `thresholds_json` | TEXT | JSON blob: `high_threshold`, `near_threshold`, `probability_threshold` |

Index: `idx_run_history_type_ts` on `(run_type, run_timestamp DESC)`
keeps the "latest operational run" and filtered history queries cheap.

### 3.2 `system_state`

Tiny key/value table for persistent system settings (e.g. drone policy
overrides). Schema: `key TEXT PRIMARY KEY, value_json TEXT NOT NULL,
updated_at TEXT NOT NULL`. `updated_at` is always produced by
`istanbul_now_iso()`.

---

## 4. How a run is persisted

Flow on every manual or scheduled run:

1. `src/pipeline/live_inference.py` builds the full result dict
   (`run_id`, `run_type`, `run_timestamp`, `target_date`, `predicted_fwi`,
   `high_risk_probability`, `high_risk_flag`, `decision_reason`,
   `raw_inputs`, `feature_values`, `validation`, `thresholds`,
   `drone_state`).
2. It calls `save_run(result)` in `src/api/db/database.py`.
3. `save_run` canonicalises `run_type` via `normalize_run_type()` so
   legacy values like `scheduled_morning` collapse to `scheduled`, then
   `json.dumps(...)` the four payload dicts and `INSERT OR REPLACE`s
   one row.
4. The scheduler and the manual `/risk/check` endpoint use the same
   function — there is exactly one write path into `run_history`.

The detection / monitoring layer **never** calls `save_run`. That
invariant is enforced by the import boundary documented in
`CORE_IDEA.md` §B.

---

## 5. How reads are hydrated

Three read helpers in `src/api/db/database.py` all route through the
same `_hydrate_run_row(row, include_payload)` helper:

- `get_run_history(limit, offset, operational_only)` — list view.
  `include_payload=False`, so the heavy JSON columns are **dropped**
  before the row leaves the DB layer. The Run History table would
  otherwise inflate by several KB per row for no benefit.
- `get_run_by_id(run_id)` — single row for the Run History detail view.
  `include_payload=True`, so every `*_json` column is `json.loads()`'d
  into its object counterpart (`raw_inputs`, `feature_values`,
  `validation`, `thresholds`).
- `get_latest_run(operational_only=True)` — **this is what powers the
  Features tab and the Overview "Last Operational Run" tile.** It
  filters to `run_type IN OPERATIONAL_RUN_TYPES` (`manual`, `scheduled`)
  and hydrates the full payload, so test / evaluation runs never show
  up as the live operational result.

The hydration happens once in the DB layer so every caller sees the
same shape — the `PredictionResult` contract documented in
`frontend/src/lib/api.ts`.

### 5.1 Why hydration lives in the DB layer

Before the Features-tab fix, hydration was scattered across the service
layer and some routes parsed `*_json` themselves while others just
forwarded the raw string columns. The Features tab bound to the raw
shape, which is why Raw API Inputs and Engineered Features showed up
empty. Centralising hydration in `_hydrate_run_row` means there is
exactly one place to change the shape, and all three read paths
(`/risk/latest`, `/history/runs`, `/history/runs/{id}`) agree.

---

## 6. Inspecting the database manually

### With the Python REPL

```powershell
"C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe"
>>> from src.api.db.database import get_connection
>>> conn = get_connection()
>>> for r in conn.execute(
...     "SELECT run_id, run_type, run_timestamp, predicted_fwi, high_risk_flag "
...     "FROM run_history ORDER BY run_timestamp DESC LIMIT 5"
... ):
...     print(dict(r))
```

### With the `sqlite3` CLI

```powershell
sqlite3 outputs\karabuk_fwi.db
sqlite> .headers on
sqlite> .mode column
sqlite> SELECT run_id, run_type, run_timestamp, predicted_fwi, high_risk_flag
   ...> FROM run_history ORDER BY run_timestamp DESC LIMIT 5;
sqlite> .schema run_history
sqlite> .quit
```

### Viewing a single run's full audit payload

```sql
SELECT run_id,
       run_timestamp,
       json_extract(validation_json, '$.is_valid')       AS valid,
       json_extract(thresholds_json, '$.high_threshold') AS high_thr,
       substr(feature_values_json, 1, 120)               AS features_preview
FROM run_history
ORDER BY run_timestamp DESC
LIMIT 1;
```

(The frontend never runs raw SQL — it always goes through the hydrated
API. These snippets are for debugging only.)

---

## 7. Looking at only operational runs

The run-type taxonomy lives in `src/api/run_types.py`:

```python
OPERATIONAL_RUN_TYPES = ("manual", "scheduled")
EVALUATION_RUN_TYPES  = ("test", "evaluation")
```

To mirror what the Overview / Features tab sees:

```sql
SELECT run_id, run_type, run_timestamp, predicted_fwi, high_risk_flag
FROM run_history
WHERE run_type IN ('manual','scheduled')
ORDER BY run_timestamp DESC
LIMIT 1;
```

Anything that returns a row here is also what `/risk/latest` will
return. If this query returns nothing but the full `run_history` has
rows, you are looking at a test-only DB and should run a manual check.

---

## 8. Timestamps and the Istanbul contract

All timestamps written to the DB must be **tz-aware Istanbul ISO 8601
strings** produced by `src/api/time_utils.py::istanbul_now_iso()` (for
wall-clock events) or `to_istanbul_iso()` (for converting an existing
datetime). Naive strings are a regression — they cause the frontend to
parse the value as local time, which shifted the scheduler cards by
three hours before the timezone fix.

A one-shot migration script exists for legacy rows:
`scripts/migrate_run_timestamps_to_istanbul.py`. It detects rows with
no `+HH:MM` / `-HH:MM` / `Z` suffix, interprets them as naive UTC, and
rewrites them as Istanbul-aware. It is idempotent — rows that already
carry an offset are skipped — so it is safe to re-run.

---

## 9. Resetting the database (last resort)

If the DB is corrupted or cluttered with experimental rows during
development:

```powershell
# Stop the backend first.
del outputs\karabuk_fwi.db
del outputs\karabuk_fwi.db-wal
del outputs\karabuk_fwi.db-shm
```

On next backend start `init_db()` recreates the schema. You lose all
run history, so do not do this in production.

A gentler option is to delete only the evaluation rows:

```sql
DELETE FROM run_history WHERE run_type IN ('test','evaluation');
```

This leaves the operational audit trail intact.

---

## 10. Summary

- One write path (`save_run`), three read paths (all routed through
  `_hydrate_run_row`).
- Heavy JSON payloads are kept out of the list endpoint and hydrated
  only for single-row reads (`/risk/latest`, `/history/runs/{id}`).
- Every timestamp is tz-aware Istanbul ISO 8601.
- `operational_only=True` keeps test and evaluation runs away from the
  Overview and Features tabs.
- Monitoring / detection code is structurally forbidden from touching
  this DB.
