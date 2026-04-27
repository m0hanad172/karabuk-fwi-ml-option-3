# Next Steps

**Current state:** Phases 1–7 complete, plus a final demo/readiness
polish pass on top of Phase 7. The polish pass added a plain-English
**Why this decision?** card and a one-click **Download brief (.md)**
on the Risk Decision tab, one-line layer-tag strips on the
**Monitoring** and **Detection Alerts** tabs so the live vs durable
distinction is immediate, and a **Key findings** card plus short
chart captions on Analytics — all derived directly from the existing
payloads, no new dependencies, no change to prediction logic /
thresholds / architecture. Phase 7 earlier had added a proper language
switcher (English default, Turkish as the second language, segmented
EN / TR toggle in the top bar, localStorage-persisted, one language
rendered at a time) applied to sidebar labels, top-bar
title/eyebrow/scope chips, page headers, and the app footer; a
persistent camera
mapping layer (`pc_camera` vs BRIO `webcam`) with fingerprint-based
advisory validation, and a docs-only backend layout clarification
(`backend/README.md` + a repository-shape note in `RUN_PROJECT.md`);
no physical code move was attempted. Phase 6 had closed out the product
/ presentation refinement pass — "Stacked v3" is the single
user-facing model name, the Long-Range View is a cited static panel
with per-card sources, the Features tab has a proper
`Feature · Meaning · Formula · Unit · Value` layout with target-date
wording, and a new **System Flow** tab gives operators an end-to-end
walkthrough of the pipeline from data fetch to dashboard. The
dashboard is presentation / demo quality, the operational audit trail
is correct end-to-end, and every tab uses the same enterprise design
system.

---

## Nothing blocks a demo today

The polish pass is verified end-to-end (`tsc --noEmit` clean; browser
DOM checks for the Why card, the two layer-tag strips, and the
Analytics additions; `/risk/latest`, `/system/scheduler`, and
`/risk/check` all returning 200 OK in the live smoke test). The
following are already true and verified:

- Both scheduler slots (11:00 and 15:00 Europe/Istanbul) register at boot
  and surface on the Scheduler card and `/system/scheduler` with explicit
  `+03:00` / `+04:00` offsets.
- Manual runs from the Risk Decision tab populate Overview, Features,
  and Run History consistently with operational-only filtering.
- Features tab renders the full 34-feature audit package for the latest
  operational run, with short explanations and mini-formulas per feature.
- Monitoring tab is structurally isolated from the prediction pipeline;
  the Drone Launch Policy strip reads `/drone/state` (driven by the
  latest operational run), not by the detection layer.
- 77 backend tests pass; frontend type-check is clean.
- Manual risk check now ~2–4 s end-to-end (was ~30 s). First camera
  frame after Start is visible in well under a second thanks to the
  capture/inference split + YOLO prewarm.
- Logitech BRIO 100 is the official project webcam (``webcam`` logical
  ID); the built-in laptop camera is ``pc_camera``. Mapping is
  operator-correctable at runtime through the Devices Detected strip
  (Auto-detect + per-row Webcam / PC Cam assign buttons) — no backend
  restart needed.
- **Camera-label inversion fixed (2026-04-19):** previously on a cold
  machine with no `data/camera_mapping.json`, the BRIO (index 0, 1080p)
  was labelled "PC Camera" and the built-in (index 1, 720p) was
  labelled "Webcam" because defaults in `cameras.py` didn't match this
  laptop's DSHOW enumeration order. The backend now runs a one-shot
  auto-detect on first boot when no mapping file exists, binding roles
  by resolution and persisting the result. Subsequent boots keep the
  existing advisory-only validation path. Resolved end-to-end —
  devices endpoint, status endpoints, and live feed routing all show
  the correct role ↔ index binding.

---

## Optional follow-ups (post-demo)

These are **not** required for the current scope. Pick any of them only
if there is a reason to extend.

1. **Docker packaging**
   - Backend Dockerfile (Python 3.11 slim + FastAPI + model artefacts)
   - Frontend Dockerfile (Node 20 + Next.js build)
   - `docker-compose.yml` wiring both services on a single bridge network
   - Right now the system runs cleanly from `.venv` + `npm run dev`, so
     Docker is only needed if you want to hand the project to someone
     who cannot set up Python/Node locally.

2. **End-to-end smoke test with live Open-Meteo**
   - A single pytest file that calls `/risk/check` against a running
     backend and asserts the response shape, the DB row, and the
     `/risk/latest` mirror. Currently the 77-test suite stays off-network
     on purpose (test rig isolation). A smoke test would exercise the
     real `fetch_weather → features → predict → save_run` path once per
     release.

3. **README.md**
   - A top-level README that pulls the highlights of `CORE_IDEA.md`,
     `RUN_PROJECT.md`, and `SQLITE_GUIDE.md` into a single entry page
     for anyone arriving at the repo cold.
   - Architecture diagram (ASCII or a single SVG) showing the three
     strictly-separated layers (prediction pipeline, live display
     weather, monitoring / detection).

4. **Dark mode toggle**
   - `globals.css` already defines dark theme tokens; the shell just
     lacks a toggle control. Would be a 30-minute addition.

5. **CSV export from Run History**
   - Download the currently visible rows as CSV. The API already
     serves the shape; this is purely a frontend feature.

6. **Browser notifications on high-risk scheduled runs**
   - Optional operator quality-of-life. Out of scope for the core
     decision-support contract.

7. **Graceful degradation when Open-Meteo is unreachable**
   - Today a failed fetch surfaces as an `ErrorAlert` on the UI and a
     structured error response from `/risk/check`. A richer strategy
     would be a short retry + cached-last-input fallback, but this has
     to be designed carefully — we explicitly do not want to reuse
     stale model inputs and present the result as live.

---

## Invariants to preserve in any future change

Every future change must keep the contract from `CORE_IDEA.md` §
"Operational invariants":

1. Two scheduled operational slots per day: **11:00** and **15:00
   Europe/Istanbul**, always both visible on the Scheduler card.
2. Only `run_type ∈ {manual, scheduled}` can appear as the Latest
   Operational Run on Overview or influence the drone policy.
3. Every timestamp that crosses the API boundary is a tz-aware Istanbul
   ISO 8601 string produced by `src/api/time_utils.py` — no naive
   datetimes, ever.
4. The prediction pipeline and the detection layer do not share any
   write path into `run_history` or `system_state`.
5. Live display weather is never used as model input.

If a proposed feature conflicts with any of these, stop and re-scope
before implementing.

---

## Key reminders

- **Do not redesign Phase 1, 2, 3, 4, 5, or 6** — all complete and verified.
- Backend: `python backend/scripts/serve.py` on port 8000 (from project root)
- Frontend: `npm run dev` in `frontend/` on port 3000
- Tests: `python -m pytest backend/tests -v` (from project root)
- Full runbook: [`RUN_PROJECT.md`](./RUN_PROJECT.md)
- DB inspection: [`SQLITE_GUIDE.md`](./SQLITE_GUIDE.md)
- Architectural contract: [`CORE_IDEA.md`](./CORE_IDEA.md)
