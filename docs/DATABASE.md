# Database

FireWatch uses SQLite for runtime persistence during the prototype/demo stage.

## Active Database

```text
backend/outputs/karabuk_fwi.db
```

This is the active local runtime database for the current project state. It is
used for local demo evidence, but it is not a repository artifact and should
not be committed.

Current table counts from the active database:

| Table | Rows |
|---|---:|
| `detection_alerts` | 19 |
| `run_history` | 31 |
| `system_state` | 2 |

## Runtime Data Warning

`backend/outputs/karabuk_fwi.db` is runtime/demo data. Alert read state,
soft-deleted alerts, manual risk checks, scheduled risk checks, and dashboard
history can change while the system is used.

Do not commit `backend/outputs/karabuk_fwi.db`. It changes during normal use
whenever the system creates a run, stores a detection alert, marks an alert as
read, or soft-deletes an alert.

Do not run `git restore -- backend/outputs/karabuk_fwi.db` unless you
intentionally want to reset the local demo database. Before any pull, reset, or
experiment that might overwrite runtime data, keep a local backup:

```powershell
Copy-Item backend\outputs\karabuk_fwi.db backend\outputs\karabuk_fwi.local.backup.db
```

For shared demo data, do not share the live runtime DB through Git. Use a demo
seed script or a clearly named demo snapshot instead.

On a personal demo machine, if the DB is still tracked in an older checkout, it
is reasonable to mark the runtime database as a local-only working copy until
the cleanup commit is pulled:

```powershell
git update-index --skip-worktree backend/outputs/karabuk_fwi.db
```

Use this only for local demo data. To make Git track the file normally again in
older branches:

```powershell
git update-index --no-skip-worktree backend/outputs/karabuk_fwi.db
```

## Why SQLite Is Used

SQLite is lightweight, serverless, easy to inspect, and does not require a
separate database server. That makes it a good choice for a final-year
prototype and local demo. For production-scale multi-user monitoring, a server
database such as PostgreSQL would be a better long-term option.

## Tables

### `run_history`

Stores each prediction run and its audit data.

Main contents:

- Run id, type, timestamp, and target date.
- Predicted FWI.
- High-risk probability and final high-risk flag.
- Decision reason and drone-ready trigger state.
- Raw inputs, engineered features, validation, and thresholds as JSON.

### `system_state`

Stores small persistent key/value state used by the backend, such as the latest
drone-ready policy state.

### `detection_alerts`

Stores durable fire/smoke detection alerts.

Real columns in the active database:

- `alert_id`
- `timestamp_iso`
- `timestamp_epoch`
- `label`
- `confidence`
- `source`
- `camera_id`
- `severity`
- `message`
- `snapshot_path`
- `is_read`
- `read_at`
- `is_deleted`
- `deleted_at`
- `detection_count`
- `detections_json`
- `raw_payload_json`

This table is independent from `run_history`. Detection alerts are operationally
related to the monitoring workflow, but SQLite does not enforce a foreign key
relationship between prediction runs and detection alerts.

Read/unread state is stored in SQLite using `is_read` and `read_at`. New alerts
start unread. When an operator opens or marks an alert as read, the backend
updates these columns so the state survives refreshes and backend restarts.

Dashboard deletion uses soft delete. `is_deleted` and `deleted_at` hide an alert
from normal dashboard views while keeping the SQLite row and snapshot path for
evidence.

## Test and Probe Databases

The following zero-byte probe/test databases are not part of the final runtime
database and should not be used in the report:

- `.tmp/pytest-runtime/.../karabuk_fwi_test.db`
- `.tmp/pytest-runtime/probe.db`
- `backend/data/test_probe.db`
- `backend/outputs/test_probe.db`
- `backend/test_probe.db`

They are temporary artifacts and should remain ignored.

## Useful SQL Queries

List tables:

```sql
SELECT name
FROM sqlite_master
WHERE type = 'table';
```

Recent prediction runs:

```sql
SELECT *
FROM run_history
ORDER BY run_timestamp DESC
LIMIT 10;
```

Recent detection alerts:

```sql
SELECT *
FROM detection_alerts
ORDER BY timestamp_iso DESC
LIMIT 10;
```

System state:

```sql
SELECT *
FROM system_state;
```

Show table schema:

```sql
PRAGMA table_info(run_history);
PRAGMA table_info(detection_alerts);
PRAGMA table_info(system_state);
```

## Future / Logical Schema

The final operational design adds tables to support the patrol-window
and grid-cell features. None of these are in the current SQLite
schema yet; they are documented in the logical ERD as a design
target only.

| Future table | Purpose |
|---|---|
| `risk_checks` | Normalised view of every scheduled / manual check (timestamp, slot, classification). |
| `patrol_windows` | One row per opened High Risk window; carries `opens_at`, `closes_at`, source check. |
| `drone_missions` | One row per 30-minute patrol slot inside a window. |
| `grid_cells` | Priority cells the drone can be sent to. |
| `stream_sources` | Configurable input sources (CCTV / PC camera / future drone). |

See [`diagrams/logical_erd.mmd`](./diagrams/logical_erd.mmd).

## Related Files

- [SQLite schema summary](./database/sqlite_schema_summary.md)
- [Current SQLite ERD](./diagrams/sqlite_erd.mmd)
- [Logical (future) ERD](./diagrams/logical_erd.mmd)
- Backend database code: `backend/src/api/db/database.py`
