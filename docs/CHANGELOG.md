# Changelog

## 2026-05-03 - Final Submission Documentation Cleanup

- Added final database documentation for the active SQLite runtime database.
- Added a schema summary generated from `backend/outputs/karabuk_fwi.db`.
- Added Mermaid ERD, system architecture, workflow, and use case diagrams.
- Added practical API reference documentation based on actual backend routes.
- Added installation and troubleshooting documentation for collaborators.
- Added final report preparation guidance with screenshot checklist.
- Updated the root README for final-year project submission and collaboration.
- Updated `.gitignore` to keep temporary probe databases ignored while allowing
  the active demo database to be tracked if required.
- Archived older duplicated run/database documentation under `docs/archive/`.

## Notes

This cleanup intentionally avoids runtime behavior changes. No API contracts,
model artifacts, thresholds, database schema, or frontend behavior were changed.
