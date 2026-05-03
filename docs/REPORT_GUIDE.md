# Report Guide

This guide helps turn the FireWatch repository into the final written report,
presentation, poster, and demo material.

## Suggested Report Structure

### 1. Introduction

Explain wildfire risk, why early monitoring matters, and why Karabuk was chosen
as the project context. Introduce FireWatch as a drone-ready wildfire risk
prediction and fire/smoke detection system.

### 2. Problem Definition

Describe the need to combine weather-based risk prediction with visual
fire/smoke monitoring. State that the current prototype uses local camera/video
input and is designed for future drone camera integration.

### 3. Literature Review

Cover:

- Fire Weather Index and wildfire risk indicators.
- Machine learning for wildfire prediction.
- Computer vision for fire/smoke detection.
- Drone-assisted monitoring systems.
- Similar dashboard or alerting systems.

### 4. Methodology

Explain:

- Data sources and weather/FWI-related features.
- Feature engineering.
- Stage 1 FWI prediction.
- Stage 2 high-risk classification.
- Risk decision thresholds.
- Fire/smoke detection pipeline.
- SQLite persistence and API/dashboard integration.

### 5. System Design

Use the diagrams in `docs/diagrams/`:

- `system_architecture.mmd`
- `workflow_diagram.mmd`
- `sqlite_erd.mmd`
- `use_case_diagram.mmd`

Explain the clean architecture layers and the separation between prediction and
detection.

### 6. Implementation

Describe:

- FastAPI backend.
- React/TypeScript dashboard.
- SQLite database.
- ML model artifacts.
- Detection module.
- Drone-ready configuration concept.

### 7. Testing and Validation

Include:

- Backend test command and result.
- Frontend lint/build command and result.
- API health check.
- Manual prediction check.
- Detection alert demo or local camera test.
- Any known local environment issues honestly.

### 8. Results and Discussion

Discuss:

- Example prediction results.
- Stored run history.
- Detection alert examples.
- Dashboard usability.
- Strengths and limitations.

### 9. Limitations

Be specific and honest. Suggested points:

- Drone hardware is not connected — the prototype is **drone-ready**
  using local camera/video input.
- The current scheduler runs the 11:00 and 15:00 risk checks;
  09:00 is in the operational design but not yet in
  `SCHEDULED_RUN_HOURS`.
- The 30-minute Drone Patrol Cycle is documented as the operational
  design and partially modelled (`DRONE_INTERVAL_MINUTES`,
  `compute_drone_state`), but the autonomous launch / inspect /
  return / standby loop is not yet implemented.
- Priority grid cells are modelled in the logical ERD only;
  they are not in the SQLite schema.
- SQLite is fine for a single-operator prototype; production-scale
  multi-user monitoring would use PostgreSQL or similar.
- Frontend lint reports a small number of pre-existing React Hooks
  warnings; they do not affect runtime behaviour.

### 10. Conclusion and Future Work

Summarize what FireWatch achieves. Future work can include:

- Connecting real drone hardware.
- Wiring the 09:00 scheduled check.
- Implementing the autonomous Drone Patrol Cycle.
- Adding the future operational tables (`risk_checks`,
  `patrol_windows`, `drone_missions`, `grid_cells`,
  `stream_sources`).
- Production database deployment.
- More model validation.
- Improved alert triage.
- Mobile notifications.
- More field testing.

### 11. References

Cite the academic and technical sources used. Include any web
references for FWI definitions, weather APIs, YOLO / Ultralytics
docs, FastAPI / SQLite docs, etc.

### 12. Appendix

Useful additions:

- API reference — `docs/API_REFERENCE.md`.
- SQLite schema summary — `docs/database/sqlite_schema_summary.md`.
- Diagram source files — `docs/diagrams/*.mmd`.
- Smoke-check output — `python backend/scripts/smoke_check.py`.

## Required Screenshots

Capture these for the report and slides:

- Dashboard main page.
- Prediction result.
- Detection/alert page.
- SQLite DB structure.
- SQLite table data.
- API health response.
- API prediction response.
- Terminal test results.
- System architecture diagram.
- Workflow diagram.
- ERD.
- Use case diagram.

## Suggested Figure Names

```text
figures/dashboard-main.png
figures/prediction-result.png
figures/detection-alerts.png
figures/sqlite-schema.png
figures/api-health.png
figures/api-risk-check.png
figures/test-results.png
figures/system-architecture.png
figures/workflow-diagram.png
figures/sqlite-erd.png
figures/use-case-diagram.png
```

## LaTeX/Overleaf Structure

Suggested project layout:

```text
main.tex
sections/
  01_introduction.tex
  02_problem_definition.tex
  03_literature_review.tex
  04_methodology.tex
  05_system_design.tex
  06_implementation.tex
  07_testing_validation.tex
  08_results_discussion.tex
  09_conclusion_future_work.tex
figures/
references.bib
```

## Drone-Ready Wording

Use this wording in the report:

> The system is designed as a drone-ready monitoring platform. In the current
> prototype, the fire/smoke detection module operates using a local camera or
> video stream. Once a drone is available, its camera stream can be configured
> as an input source without changing the core detection and alerting pipeline.

Avoid saying the current system is fully drone-based unless real drone hardware
is connected and demonstrated.
