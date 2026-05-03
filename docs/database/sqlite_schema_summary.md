# SQLite Schema Summary

Generated from the active SQLite database:

```text
backend/outputs/karabuk_fwi.db
```

Database size observed during audit: `114688` bytes.

## Tables

| Table | Rows | Purpose |
|---|---:|---|
| `detection_alerts` | 13 | Fire/smoke detection alert log |
| `run_history` | 30 | Prediction run audit history |
| `system_state` | 2 | Small persistent key/value system state |

## `detection_alerts`

Primary key: `alert_id`

Foreign keys: none

| Column | Type | Primary Key | Not Null | Default |
|---|---|---|---|---|
| `alert_id` | TEXT | Yes | No | - |
| `timestamp_iso` | TEXT | No | Yes | - |
| `timestamp_epoch` | REAL | No | No | - |
| `label` | TEXT | No | Yes | - |
| `confidence` | REAL | No | Yes | - |
| `source` | TEXT | No | Yes | - |
| `camera_id` | TEXT | No | No | - |
| `severity` | TEXT | No | No | - |
| `message` | TEXT | No | No | - |
| `snapshot_path` | TEXT | No | No | - |
| `is_read` | INTEGER | No | Yes | 0 |
| `read_at` | TEXT | No | No | - |
| `detection_count` | INTEGER | No | Yes | 0 |
| `detections_json` | TEXT | No | No | - |
| `raw_payload_json` | TEXT | No | No | - |

## `run_history`

Primary key: `run_id`

Foreign keys: none

| Column | Type | Primary Key | Not Null | Default |
|---|---|---|---|---|
| `run_id` | TEXT | Yes | No | - |
| `run_type` | TEXT | No | Yes | - |
| `run_timestamp` | TEXT | No | Yes | - |
| `target_date` | TEXT | No | Yes | - |
| `predicted_fwi` | REAL | No | No | - |
| `high_risk_probability` | REAL | No | No | - |
| `high_risk_flag` | INTEGER | No | No | - |
| `decision_reason` | TEXT | No | No | - |
| `drone_triggered` | INTEGER | No | No | 0 |
| `raw_inputs_json` | TEXT | No | No | - |
| `feature_values_json` | TEXT | No | No | - |
| `validation_json` | TEXT | No | No | - |
| `thresholds_json` | TEXT | No | No | - |

## `system_state`

Primary key: `key`

Foreign keys: none

| Column | Type | Primary Key | Not Null | Default |
|---|---|---|---|---|
| `key` | TEXT | Yes | No | - |
| `value_json` | TEXT | No | Yes | - |
| `updated_at` | TEXT | No | Yes | - |

## Relationship Note

The active database has no SQLite-enforced foreign keys. Relationships are
logical and operational:

- `run_history` supports prediction audit and dashboard history.
- `detection_alerts` supports monitoring and alert review.
- `system_state` stores the latest small state snapshots used by the backend.
