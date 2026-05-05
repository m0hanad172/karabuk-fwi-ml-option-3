# Architecture

FireWatch is organized as a simple end-to-end wildfire monitoring prototype.
The main runtime is a FastAPI backend, a React dashboard, trained ML artifacts,
a fire/smoke detection module, and a SQLite database.

## System Overview

The system has two main flows:

1. Wildfire risk prediction from weather and FWI-related features.
2. Fire/smoke detection from a local camera or video stream, with future drone
   camera input supported by configuration.

These flows meet in the dashboard and database, but they should stay logically
separate. Prediction results are stored in `run_history`; detection evidence is
stored in `detection_alerts`.

## Clean Architecture Layers

| Layer | Location | Responsibility |
|---|---|---|
| Data source | `backend/src/data/` | Weather and supporting data collection |
| Feature engineering | `backend/src/features/` | Build and validate model input features |
| ML prediction | `backend/src/inference/`, `backend/src/models/` | Load model artifacts and run predictions |
| Risk decision | `backend/src/models/decision.py`, `backend/src/pipeline/` | Convert FWI/probability into high-risk decisions |
| Fire/smoke detection | `backend/src/monitoring/` | Camera streams, YOLO detection, alert creation |
| API/backend | `backend/src/api/` | FastAPI routes, scheduler, services, runtime config |
| Persistence | `backend/src/api/db/`, `backend/outputs/karabuk_fwi.db` | SQLite schema and queries |
| Frontend/dashboard | `frontend/` | Operator dashboard and visual workflows |
| Tests | `backend/tests/` | Unit/API/architecture checks |
| Documentation | `docs/` | Final report support, setup, database, diagrams |

This is a clean and understandable structure for a final-year project. It is
not over-engineered: modules are separated by responsibility, but the project
still remains easy to run locally.

## Backend and Frontend Separation

The backend owns data processing, ML inference, detection, persistence, and
API responses. The frontend is a dashboard client that calls the backend and
renders the result. It should not duplicate prediction logic or maintain a
separate source of truth.

## Prediction Flow

1. Fetch or prepare weather/FWI-related input data.
2. Build engineered features.
3. Validate feature completeness.
4. Run the Stage 1 FWI regression model.
5. Run the Stage 2 high-risk classifier.
6. Apply risk decision thresholds.
7. Store the run in `run_history`.
8. Display the result in the dashboard.

## Detection and Alert Flow

1. Open a local camera/video stream.
2. Run fire/smoke detection on frames.
3. Create an alert when detection conditions are met.
4. Store alert metadata in `detection_alerts`.
5. Store or reference snapshot evidence when available.
6. Display alerts in the dashboard.
7. Allow the operator to mark alerts as read/unread.

## Operational Logic (Final Design)

FireWatch is a **prediction-driven monitoring system**, not two
independent modules. Risk prediction decides what monitoring should
happen, and monitoring records evidence in the database.

### Scheduled risk checks

Three scheduled checks per day, all in **Europe/Istanbul**:

| Slot | Time | Purpose |
|---|---|---|
| Morning | 09:00 | Early-day risk read — sets the tone for the morning. |
| Midday | 11:00 | Operational check — high-risk hours start. |
| Afternoon | 15:00 | Late-day check — most fires occur in this window. |

Each check follows the same flow: fetch latest weather → build features
→ run Stage 1 + Stage 2 → classify risk → write a row to
`run_history` → update `system_state` → render in the dashboard.

### Manual risk check

An operator can run a manual check at any time from the dashboard
(Risk Decision tab → **Run Manual Check**) or via
`POST /risk/check`. The `run_type` is recorded as `manual`. If the
manual check returns **High Risk** and the operator passes
`allow_drone_trigger=true`, the same patrol-window rules apply as a
scheduled check.

### Risk classes and actions

| Risk class | Drone patrol | CCTV / fixed cameras | Persisted |
|---|---|---|---|
| Low / Moderate | No automatic patrol | Always-on | `run_history` row |
| High | Open Drone Patrol Window | Always-on | `run_history` row + `system_state.latest_drone_state` |

### Drone Patrol Window

A High Risk classification opens a **patrol window** that runs from
the triggering check until the next scheduled check. Special case:
a 15:00 high-risk check ends its window at **17:00**, so patrol
never runs overnight.

| Trigger | Window opens at | Window closes at |
|---|---|---|
| 09:00 high risk | 09:00 | 11:00 |
| 11:00 high risk | 11:00 | 15:00 |
| 15:00 high risk | 15:00 | 17:00 (operational cutoff) |
| Manual high risk | now | next scheduled check or 17:00, whichever sooner |

### Drone Patrol Cycle (future production design)

The drone does not fly continuously. In the future production design,
while the window is open, the system can run a **30-minute patrol cycle**:

1. **Launch** — short patrol over selected priority grid cells.
2. **Inspect** — fire/smoke detection on the drone/video stream.
3. **Return** — back to base.
4. **Standby / battery preparation / battery swap** — until the next
   30-minute slot.

Example for a 09:00 high-risk classification:

```
09:00  Risk check returns High Risk → patrol window opens.
09:00  Launch patrol  →  09:10–09:15 return / land.
09:15  Standby / battery preparation.
09:30  Launch patrol.
10:00  Launch patrol.
10:30  Launch patrol.
11:00  New scheduled risk check. Re-evaluate.
```

### CCTV vs drone roles

| Role | What it is | When it runs |
|---|---|---|
| **CCTV / fixed cameras** | Always-on local cameras at fixed monitoring points. | 24/7, independent of the risk classification. |
| **Drone patrol** | Risk-triggered mobile monitoring of priority grid cells. | Only inside an open patrol window. |

Both share the same fire/smoke detection pipeline; both write into
`detection_alerts`. The dashboard treats them as different alert
sources (`source=webcam` / `source=pc_camera` / `source=drone`).

### Operator-controlled drone-ready prototype

The current prototype is operator-in-the-loop. FireWatch can run in mock
drone mode by default, or in Tello mode when explicitly configured. Stream
start means video input only; it does **not** mean physical takeoff. Physical
drone movement remains operator-controlled, and launch requires operator
confirmation.

The **Run Demo Patrol** trigger is separate from the production wildfire risk
decision. It allows the drone workflow to be tested during low-risk days
without changing the real High Risk threshold. In mock mode it simulates the
patrol. In Tello mode, the controlled route is short, configurable, and blocked
unless demo patrol, takeoff permission, battery, connection, and operator
confirmation gates all pass.

The old project is used only as a reference for Tello connection, stream
start/stop, frame reading, MJPEG streaming, and YOLO-on-drone-frame detection.
FireWatch does not copy the old global-state drone control style.

## Limitations and Future Improvements

Honest gap between the **operational design above** and the
**current implementation**:

| Operational design | Current implementation |
|---|---|
| 3 scheduled checks at 09:00, 11:00, 15:00 | Implemented in `SCHEDULED_RUN_HOURS = [9, 11, 15]`. |
| Automated 30-minute patrol cycle | `DRONE_INTERVAL_MINUTES = 30` is defined and `compute_drone_state` returns `next_launch_time`. The full launch / inspect / return / standby orchestration remains future work and must not auto-launch real hardware. |
| 17:00 cutoff for the 15:00 high-risk window | Not yet enforced in code. |
| Priority grid cells | Modelled in the logical ERD (`docs/diagrams/logical_erd.mmd`), not yet in the SQLite schema. |
| Manual high-risk check triggers patrol | The `allow_drone_trigger` flag is wired through the API; default is `False` so the operator must opt in. |

Additional limitations:

- Drone hardware is optional; mock mode is the safe default.
- Current demo uses local camera/video or operator-controlled drone stream input.
- Autonomous waypoint/grid patrol is not implemented.
- SQLite is suitable for prototype/demo use; production deployment
  should consider PostgreSQL.

## Database Role

SQLite is the runtime persistence layer. It stores:

- Prediction and decision history in `run_history`.
- Current or latest system state in `system_state`.
- Fire/smoke detection alerts in `detection_alerts`.

There are no enforced SQLite foreign keys between these tables. Relationships
are operational and logical: the dashboard reads from all three areas, but
prediction and detection write paths remain separate.

## Strengths

- End-to-end pipeline from data input to dashboard display.
- Clear backend/frontend split.
- Separate ML prediction and detection modules.
- Durable SQLite storage for demo and reporting.
- Practical API coverage for collaborators.
- Drone-ready wording and design without overstating hardware status.

## Diagrams

- [`diagrams/system_architecture.mmd`](./diagrams/system_architecture.mmd) — six-layer system view.
- [`diagrams/workflow_diagram.mmd`](./diagrams/workflow_diagram.mmd) — scheduled check + patrol-window flow.
- [`diagrams/use_case_diagram.mmd`](./diagrams/use_case_diagram.mmd) — actors and use cases.
- [`diagrams/sqlite_erd.mmd`](./diagrams/sqlite_erd.mmd) — current real schema.
- [`diagrams/logical_erd.mmd`](./diagrams/logical_erd.mmd) — future operational schema (design only).

## Risky Areas

Changes in these areas should be reviewed before editing:

- Model artifacts and thresholds.
- API request/response contracts.
- SQLite schema and migrations.
- Backend import paths and project structure.
- Detection runtime behavior.
- Frontend dashboard behavior.
