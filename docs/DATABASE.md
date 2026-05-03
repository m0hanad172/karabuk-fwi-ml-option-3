# Database

FireWatch uses SQLite for runtime persistence during the prototype/demo stage.

## Active Database

```text
backend/outputs/karabuk_fwi.db
```

This is the active real database for the current project state. It is used for
final documentation and report evidence.

Current table counts from the active database:

| Table | Rows |
|---|---:|
| `detection_alerts` | 13 |
| `run_history` | 30 |
| `system_state` | 2 |

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
- `detection_count`
- `detections_json`
- `raw_payload_json`

This table is independent from `run_history`. Detection alerts are operationally
related to the monitoring workflow, but SQLite does not enforce a foreign key
relationship between prediction runs and detection alerts.

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

## Related Files

- [SQLite schema summary](./database/sqlite_schema_summary.md)
- [SQLite ERD](./diagrams/sqlite_erd.mmd)
- Backend database code: `backend/src/api/db/database.py`
