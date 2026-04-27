# RUN_PROJECT

Practical, exact steps for running the Karabük FWI **Stacked v3** system
locally. All operational times are **Europe/Istanbul** (TRT).

## Repository shape

```
frontend/   Next.js 16 dashboard (see frontend/README.md if present)
backend/    Docs only — see backend/README.md for the logical backend layout.
            The backend source code lives at the repo root in src/ + scripts/
            + configs/ + models/ + tests/. It is kept there because every
            Python import is absolute (from src.*, from configs.*), and
            moving it would break imports, tests, paths, and notebooks.
```

---

## 0. Prerequisites

- Windows 10/11 (paths below use the Windows layout)
- Python 3.11+ — the canonical interpreter for this project is:
  ```
  C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe
  ```
  A `.venv` lives in the repo root for convenience.
- Node.js 20+ and npm 10+
- Open network access to `api.open-meteo.com` and `archive-api.open-meteo.com`

---

## 1. Activate the local `.venv`

From the repo root `E:\karabuk-fwi-ml-option-3`:

```powershell
# PowerShell
.\.venv\Scripts\Activate.ps1
```

```cmd
:: cmd.exe
.\.venv\Scripts\activate.bat
```

You should see `(.venv)` in the prompt. If the venv is missing:

```powershell
"C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> **Note:** the backend, tests, and scripts all work with the direct interpreter path too, so activation is optional. Direct form:
> ```
> "C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe" <command>
> ```

---

## 2. Install requirements

Backend:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Frontend:

```powershell
cd frontend
npm install
cd ..
```

---

## 3. Run the backend

From the repo root:

```powershell
"C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe" scripts/serve.py
```

- API root: <http://localhost:8000>
- OpenAPI docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/system/health>

The backend boots the APScheduler with two Istanbul-time operational slots
(11:00 and 15:00) automatically.

---

## 4. Run the frontend

In a second terminal:

```powershell
cd frontend
npm run dev
```

- Dashboard: <http://localhost:3000>
- Default landing page: **Overview**
- Sidebar order: Overview → Impact & Context → Risk Decision → Features →
  Analytics → Run History → Monitoring → System

All timestamps in the UI display in **Europe/Istanbul**.

---

## 5. Verify the scheduler

Hit the status endpoint:

```powershell
curl http://localhost:8000/system/scheduler
```

Expected shape:

```json
{
  "running": true,
  "jobs": [
    {
      "id": "scheduled_morning_run",
      "name": "Scheduled morning run (11:00)",
      "next_run_time": "2026-04-16T11:00:00+03:00"
    },
    {
      "id": "scheduled_afternoon_run",
      "name": "Scheduled afternoon run (15:00)",
      "next_run_time": "2026-04-15T15:00:00+03:00"
    }
  ]
}
```

Every `next_run_time` string MUST carry an explicit `+03:00` offset (or
`+04:00` during DST). If one is missing, time handling has regressed —
see `src/api/time_utils.py`.

Or look at the **Scheduler** card on the Overview tab, which shows the
same values formatted as local Istanbul time.

---

## 6. Run a manual risk check

Three ways to trigger an operational `manual` run:

1. **UI:** Risk Decision tab → click **Run Manual Check**.
2. **curl:**
   ```powershell
   curl -X POST http://localhost:8000/risk/check ^
        -H "Content-Type: application/json" ^
        -d "{\"allow_drone_trigger\": false}"
   ```
3. **Docs playground:** <http://localhost:8000/docs> → `POST /risk/check` → Try it out.

After a successful run:
- The Overview tab's "Last Operational Run" tile updates.
- A new row appears in Run History with the Istanbul run timestamp.
- The run is `run_type="manual"`, which means it IS eligible to influence
  the drone launch policy (subject to `allow_drone_trigger`).

---

## 7. Run tests

```powershell
"C:/Users/HICOM/Desktop/Pyhon rs/inst/python.exe" -m pytest tests/ -v
```

Current baseline: **77 backend tests passing** across prediction, API,
monitoring, run-type taxonomy and JSON serialization safety.

Test runs use an isolated SQLite database via `KARABUK_DB_PATH` set in
`tests/conftest.py`, so they never pollute `outputs/karabuk_fwi.db`.

---

## 8. Monitoring: camera / drone feeds

The monitoring layer is **strictly separate** from the prediction
pipeline — it never writes `predicted_fwi` or `high_risk_flag`.

**Start/stop feeds from the UI:**

- Navigate to **Monitoring** in the sidebar.
- Three feed cards: Drone Camera, Webcam Feed, PC Camera Feed.
- Each card has a **Start feed** / **Stop feed** button.
- Streams are served as MJPEG at:
  - `GET /monitoring/drone/feed`
  - `GET /monitoring/cameras/webcam/feed`
  - `GET /monitoring/cameras/pc_camera/feed`

**Drone policy view (read-only):**

- The Monitoring tab's top "Drone Launch Policy" strip reads
  `GET /drone/state`, which is driven by the latest operational
  prediction — NOT by the detection layer.

**Fire detection notifications:**

- `GET /monitoring/notifications` returns the ring buffer (last 200
  events). The dashboard polls every 5 seconds.
- Detection timestamps are always Istanbul-local.

---

## 9. Important URLs, endpoints, and pages

### Dashboard pages
| Page | Purpose |
|---|---|
| `/` Overview | Executive summary + KPIs + scheduler + weather |
| Impact & Context | Motivation: Karabük 2025 wildfire impact (static) |
| Risk Decision | Manual operational run + decision explanation |
| Features | Raw inputs, engineered features, Stage 2 meta-features |
| Analytics | 2012–2025 FWI trend, yearly and seasonal charts |
| Run History | Full audit log with expandable rows |
| Monitoring | Drone / Webcam / PC Camera operations console |
| System | Model metadata, thresholds, scheduler, health |

### Backend endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `/system/health` | GET | Stage 1/2/DB healthcheck |
| `/system/model` | GET | Model metadata + thresholds |
| `/system/scheduler` | GET | APScheduler status + next runs |
| `/risk/check` | POST | Trigger an operational `manual` run |
| `/risk/latest` | GET | Latest operational prediction only |
| `/history` | GET | Paginated run history |
| `/history/{run_id}` | GET | Run detail (validation, features, thresholds) |
| `/weather/live` | GET | Display-only current weather snapshot |
| `/drone/state` | GET | Read-only drone launch policy |
| `/monitoring/...` | misc | Detection layer feeds + notifications |

### Operational timing contract
- Morning run: **11:00** Istanbul, `run_type = scheduled`
- Afternoon run: **15:00** Istanbul, `run_type = scheduled`
- Manual runs: on-demand, `run_type = manual`
- Test/evaluation runs: NEVER appear in Overview or drone policy.
