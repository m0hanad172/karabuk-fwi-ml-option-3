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

## Drone-Ready Design

The system is designed as a drone-ready monitoring platform. In the current
prototype, the fire/smoke detection module operates using a local camera or
video stream. Once a drone is available, its camera stream can be configured as
an input source without changing the core detection and alerting pipeline.

This keeps the current prototype honest while still showing how the system can
be extended to drone hardware.

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

## Limitations and Future Improvements

- Drone hardware is not currently connected.
- Current detection input is local camera/video stream.
- SQLite is suitable for prototype/demo use, but a larger deployment should
  consider PostgreSQL or another managed database.
- Frontend lint currently reports existing React hook issues.
- Test execution depends on local filesystem permissions for temporary SQLite
  files.
- Future work can improve model validation, add production deployment docs,
  improve alert review workflows, and add more visual QA screenshots.

## Risky Areas

Changes in these areas should be reviewed before editing:

- Model artifacts and thresholds.
- API request/response contracts.
- SQLite schema and migrations.
- Backend import paths and project structure.
- Detection runtime behavior.
- Frontend dashboard behavior.
