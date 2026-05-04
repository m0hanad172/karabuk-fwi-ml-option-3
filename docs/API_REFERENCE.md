# API Reference

Base URL during local development:

```text
http://localhost:8000
```

Interactive OpenAPI documentation is available at:

```text
http://localhost:8000/docs
```

## Root

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Basic service metadata |

## System

| Method | Path | Purpose |
|---|---|---|
| GET | `/system/health` | Health status for models and database |
| GET | `/system/model` | Model names, feature counts, thresholds, and metrics |
| GET | `/system/scheduler` | Scheduler state and next run information (09:00, 11:00, 15:00 Europe/Istanbul) |
| GET | `/system/config` | Public runtime flags for the frontend |

Example:

```powershell
curl http://localhost:8000/system/health
```

## Risk Prediction

| Method | Path | Purpose |
|---|---|---|
| POST | `/risk/check` | Run a manual wildfire risk check |
| GET | `/risk/latest` | Return the latest operational prediction |

`POST /risk/check` accepts a JSON body:

```json
{
  "target_date": "2026-05-03",
  "allow_drone_trigger": false
}
```

Both fields are optional. `target_date` defaults to today and
`allow_drone_trigger` defaults to `false`.

Example:

```powershell
curl -X POST http://localhost:8000/risk/check -H "Content-Type: application/json" -d "{\"allow_drone_trigger\":false}"
```

Response summary:

- `run_id`
- `run_type`
- `run_timestamp`
- `target_date`
- `predicted_fwi`
- `high_risk_probability`
- `high_risk_flag`
- `decision_reason`
- `thresholds`

## History and Analytics

| Method | Path | Purpose |
|---|---|---|
| GET | `/history/runs` | List prediction runs |
| GET | `/history/runs/{run_id}` | Return one full run detail |
| GET | `/history/analytics` | Return historical FWI analytics |

Optional query parameters for `/history/runs`:

- `limit`
- `offset`

Example:

```powershell
curl "http://localhost:8000/history/runs?limit=10&offset=0"
```

## Weather

| Method | Path | Purpose |
|---|---|---|
| GET | `/weather/live` | Display-only current weather snapshot |

The live weather endpoint is for dashboard display. It is not the model input
path.

## Drone-Ready State

| Method | Path | Purpose |
|---|---|---|
| GET | `/drone/state` | Latest drone-ready policy state from risk checks |
| GET | `/drone/status` | Operator-controlled drone adapter status |
| POST | `/drone/connect` | Connect configured adapter; mock mode succeeds without hardware |
| POST | `/drone/disconnect` | Disconnect configured adapter |
| POST | `/drone/stream/start` | Start drone/video stream; does not take off |
| POST | `/drone/stream/stop` | Stop drone/video stream |
| GET | `/drone/feed` | Drone/video MJPEG feed |
| POST | `/drone/manual-command` | Manual command, blocked unless enabled by config |
| POST | `/drone/emergency-stop` | Idempotent emergency stop |
| GET | `/drone/patrol/state` | Patrol recommendation state; no physical launch |

The response carries `active_alert_window` (whether a High Risk
patrol window is open), `drone_status`
(`ACTIVE_CYCLE` / `STANDBY`), `drone_interval_minutes` (30 when
active), `next_launch_time`, and a human-readable `reason`. The
current prototype does not require real drone hardware to be
connected — see the operational logic in
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

Drone adapter endpoints are operator-controlled. `DRONE_MODE=mock` is the
default. `DRONE_MODE=tello` prepares DJI Tello stream integration, but physical
launch still requires operator confirmation and is not automatic.

## Monitoring and Detection

| Method | Path | Purpose |
|---|---|---|
| GET | `/monitoring/cameras` | List configured camera roles and status |
| GET | `/monitoring/cameras/devices` | Probe local camera indices |
| GET | `/monitoring/runtime` | Runtime environment hints for monitoring |
| POST | `/monitoring/cameras/{cam_id}/remap` | Change a camera OpenCV index |
| POST | `/monitoring/cameras/auto-detect` | Auto-assign local camera roles |
| GET | `/monitoring/cameras/{cam_id}/status` | Status for one camera |
| POST | `/monitoring/cameras/{cam_id}/start` | Start a camera capture loop |
| POST | `/monitoring/cameras/{cam_id}/stop` | Stop a camera capture loop |
| GET | `/monitoring/cameras/{cam_id}/feed` | MJPEG camera stream |
| GET | `/monitoring/drone/status` | Drone stream status |
| POST | `/monitoring/drone/start` | Start drone stream adapter |
| POST | `/monitoring/drone/stop` | Stop drone stream adapter |
| GET | `/monitoring/drone/feed` | MJPEG drone stream |
| GET | `/monitoring/notifications` | Recent in-memory detection notifications |

## Detection Alerts

| Method | Path | Purpose |
|---|---|---|
| GET | `/monitoring/alerts` | List durable detection alerts |
| GET | `/monitoring/alerts/summary` | Alert totals and read/unread counts |
| GET | `/monitoring/alerts/latest` | Latest detection alert |
| POST | `/monitoring/alerts/test` | Create a synthetic demo alert when enabled |
| POST | `/monitoring/alerts/mark-all-read` | Mark every alert as read |
| POST | `/monitoring/alerts/{alert_id}/read` | Mark one alert as read |
| POST | `/monitoring/alerts/{alert_id}/unread` | Mark one alert as unread |
| DELETE | `/monitoring/alerts/{alert_id}` | Soft-delete one alert from dashboard views |
| GET | `/monitoring/alerts/{alert_id}` | Get one alert with detection details |

Optional query parameters for `/monitoring/alerts`:

- `limit`
- `offset`
- `source`
- `filter=all|unread|read`

Example:

```powershell
curl "http://localhost:8000/monitoring/alerts?limit=10&filter=unread"
```

Alert responses include `is_read`, `read`, and `read_at`. Calling
`POST /monitoring/alerts/{alert_id}/read` is idempotent and persists the read
state in SQLite.

Normal alert and notification endpoints hide soft-deleted alerts. Deletion sets
`is_deleted` and `deleted_at`; it does not remove the SQLite evidence row or
snapshot file.
