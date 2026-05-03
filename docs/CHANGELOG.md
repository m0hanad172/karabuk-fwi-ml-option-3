# Changelog

Project-level changelog. Code commits live in `git log`; this file
captures the milestones in plain English so a reviewer or collaborator
can read the project's history in one page.

## 2026-05-03 — Operational logic documented + presentation polish

- **Documented final operational logic** in `ARCHITECTURE.md`:
  three scheduled risk checks (09:00 / 11:00 / 15:00 Europe/Istanbul),
  manual risk checks, the High-Risk Drone Patrol Window, the
  30-minute Drone Patrol Cycle, the 17:00 cutoff for the 15:00 slot,
  and the CCTV-vs-drone roles.
- **Honest limitations** added: code currently runs the 11:00 and
  15:00 slots; the 30-minute patrol orchestration is design-only
  (drone hardware not connected); priority grid cells are modelled
  in the logical ERD only.
- **Diagrams** updated to match the operational logic
  (`system_architecture.mmd`, `workflow_diagram.mmd`,
  `use_case_diagram.mmd`, `sqlite_erd.mmd`).
- **New `logical_erd.mmd`** documenting the future operational schema
  (`risk_checks`, `patrol_windows`, `drone_missions`, `grid_cells`,
  `stream_sources`, `detection_alerts`, `system_state`).
- **Frontend wording polish** — short presentation-ready labels and
  empty states, no UX redesign.
- **Doc structure tightened**:
  - `RUN_PROJECT.md` → `INSTALLATION.md`
  - `SQLITE_GUIDE.md` → `DATABASE.md`
  - `CORE_IDEA.md`, `DEPLOYMENT_PLAN.md`, `PROJECT_BRIEF.md` moved to
    `docs/archive/` (preserved verbatim).
- New `API_REFERENCE.md`, `REPORT_GUIDE.md`, and this `CHANGELOG.md`.

## 2026-05-02 — Final-year submission documentation

- Active database documentation (`backend/outputs/karabuk_fwi.db`).
- Generated `database/sqlite_schema_summary.md` from the live DB.
- Added Mermaid ERD, system architecture, workflow, use-case diagrams.
- API reference based on actual backend routes.
- Installation + troubleshooting docs for collaborators.
- Report-preparation guide with screenshot checklist.
- Root README rewritten in simple English for collaborators.
- `.gitignore` keeps probe DBs out while allowing the active DB.

## 2026-05-01 — Detection Alerts moved to SQLite

- New `detection_alerts` table with `is_read`, `read_at`,
  `severity`, `snapshot_path`, full `detections_json` payload.
- `notifications.py` rewritten as SQLite-backed; in-memory ring
  buffer is rehydrated from SQLite at every backend boot.
- Idempotent migration of legacy `alerts.jsonl` rows on first
  startup (matched by `alert_id`); JSONL preserved on disk.
- Frontend Detection Alerts tab gets All / Unread / Read filter
  pills, per-row mark-as-read, and a bulk Mark-all-read button.

## 2026-04-30 — Local Hardware Mode adopted

- Removed all Docker artefacts (`docker-compose.yml`, both
  Dockerfiles, both `.dockerignore` files, the docker-validate CI job).
- Added PowerShell helpers under `scripts/`: `check_ports.ps1`,
  `start_backend.ps1`, `start_frontend.ps1`.
- Documentation rewritten around running the backend directly on
  the Windows host so OpenCV/DSHOW can reach the live webcam.

## 2026-04-29 — Repository restructure

- Backend code consolidated into `backend/`.
- Long-form docs collected into `docs/`.
- Pre-restructure DB safely migrated to `backend/outputs/`.
- Smoke check script added (`backend/scripts/smoke_check.py`).
- 110 backend tests passing.

## Notes

This changelog only covers documentation and operational changes.
No commit ever changes ML model artefacts, thresholds, API
contracts, the SQLite schema, or detection runtime behaviour
without an explicit, separate review.
