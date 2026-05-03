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
| GET | `/system/scheduler` | Scheduler state and next run information |
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

This endpoint reports system state. The current prototype does not require
drone hardware to be connected.

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
