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

### 9. Conclusion and Future Work

Summarize what FireWatch achieves. Future work can include:

- Connecting real drone hardware.
- Production database deployment.
- More model validation.
- Improved alert triage.
- Mobile notifications.
- More field testing.

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
