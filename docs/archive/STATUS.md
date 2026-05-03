# Project Status

**Last updated:** 2026-04-19 · Phase 7 demo/readiness polish

---

## Phase 7 — Demo/readiness polish (2026-04-19)

Narrow, safe pass on top of the existing Phase 7 bilingual/camera checkpoint.
No change to prediction logic, thresholds, architecture, or dependencies.

### Risk Decision — "Why this decision?" + Markdown brief
- New **Why this decision?** card inserted between the 3-KPI tile row and
  the existing Decision Explanation card in
  `frontend/src/components/tabs/risk-decision.tsx`.
- Derives state from the live `/risk/latest` payload and the returned
  thresholds only — no hard-coded numbers, no fake precision:
  `fwiAboveHigh`, `fwiInGreyZone`, `probAboveThr` feed a 4-variant verdict
  sentence, three tone-accented `ComparisonRow`s (FWI vs high / FWI vs
  grey zone / probability vs threshold), and a 4-variant branch
  explanation ("NORMAL" / "HIGH — FWI already above threshold" / "HIGH —
  safety classifier rescued from grey zone" / "HIGH — both rules fired").
- **Download brief (.md)** button on the Decision Explanation card
  header. Pure-browser Blob + `URL.createObjectURL` + temporary anchor,
  no new dependencies. Filename pattern
  `decision-brief-<target_date>-<run_id>.md`. Body lines: run ID, run
  type, run timestamp (Istanbul), target date, verdict, predicted FWI,
  probability, thresholds, branch explanation, backend `decision_reason`.

### Monitoring / Detection Alerts — layer-tag strips
- `monitoring-drone.tsx`: one-line secondary-tone strip at the top —
  **"Live detection console."** Plain-English distinction pointing to
  Detection Alerts for the durable record.
- `detection-alerts.tsx`: mirrored primary-tone strip — **"Durable
  evidence log."** Points back to Monitoring for live feeds.
- Both strips use `role="note"` for accessibility and reuse the existing
  design tokens — no new components.

### Historical Analytics — Key findings + chart captions
- New `KeyFindingsCard` above the summary strip in
  `historical-analytics.tsx`. Four bulleted findings computed from the
  aggregated payload only (peak fire season, riskiest month on average,
  share of high-risk days, long-term trend direction).
- Long-term trend uses an OLS least-squares slope sign with a flat band
  = `max(0.05, |mean| * 0.005)`. Returns `"rising" | "falling" | "flat"`
  — direction only, no slope number, no fake precision.
- Short explanatory captions added under the three charts that were
  unlabelled (monthly trend, yearly breakdown, seasonal profile).
- Source footer notes that numbers come directly from the analytics
  payload — no model inference, no interpolation.

### Verification
- `tsc --noEmit` clean.
- Live smoke test on a fresh backend + frontend:
  * `/` → 200, `/risk/latest` → run `4133789a1150` (FWI 0.8, 0.0%,
    NORMAL), `/system/scheduler` → both 11:00 and 15:00 slots at
    Europe/Istanbul.
  * Manual `/risk/check` end-to-end latency **4.4 s** (within the
    Phase 5 2–4 s target for a warm server; first call included the
    Open-Meteo round trip).
  * Risk Decision tab: Why card verified in the DOM; branch text
    matches the backend `decision_reason`.
  * Monitoring tab: layer-tag strip rendered ("Live detection
    console…").
  * Detection Alerts tab: layer-tag strip rendered ("Durable evidence
    log…").
  * Analytics tab: Key findings card + chart captions verified in
    source; the live API call was blocked by an unrelated DSHOW
    camera-worker hang on the uvicorn reloader (known Windows pattern;
    not code-related, not a regression from this polish pass).
- No console errors in the browser (Fast Refresh logs only).

---

## Phase 7 checkpoint (2026-04-19)

### Backend structure clarification (docs-only, no code move)
- Added `backend/README.md` describing the logical backend layout
  (`src/`, `scripts/`, `configs/`, `models/`, `data/`, `tests/`) and why
  a physical move was deferred (absolute imports, `serve.py` path
  wiring, pytest discovery, paths in `configs/paths.py`).
- Added a "Repository shape" note at the top of `RUN_PROJECT.md`.

### Persistent camera mapping (`pc_camera` vs `webcam`)
- New `src/monitoring/camera_mapping.py` with fingerprint dataclass
  (width × height × fps ±2), `load/save/apply/validate` helpers.
- `data/camera_mapping.json` path registered in `configs/paths.py`.
- `src/monitoring/cameras.py` applies persisted mapping on import and
  re-saves after `remap_camera` / `auto_detect_cameras`.
- `src/api/main.py` lifespan runs a daemon-thread advisory validator
  that only logs stale roles — never mutates the mapping.

### First-boot camera mapping bootstrap (resolves inverted-labels bug)
- **Root cause:** on this Windows laptop, the Logitech BRIO enumerates
  at index 0 and the built-in camera at index 1 — the opposite of the
  hard-coded defaults in `cameras.py` (`pc_camera=0`, `webcam=1`).
  Without a persisted mapping file, `apply_mapping()` was a no-op at
  import, so the defaults won and the UI showed the BRIO (1920×1080)
  labelled as "PC Camera" and the built-in (1280×720) labelled as
  "Webcam".
- **Fix layer:** startup mapping restore. Auto-detect, remap, frontend
  label binding, and feed routing were all correct — they just had the
  wrong roles to display.
- **Change:** `camera_mapping.mapping_file_exists()` helper + updated
  `_validate_camera_mapping()` in `src/api/main.py`. On first boot,
  when no mapping file exists, it now runs `auto_detect_cameras()` once
  so logical roles bind to physical devices by resolution
  (highest-res → `webcam`, remaining → `pc_camera`) and the mapping is
  persisted. Subsequent boots follow the existing "validate, don't
  mutate" path.
- **Verified end-to-end:** `GET /monitoring/cameras/devices` now
  returns `index 0 (1920×1080) → webcam`, `index 1 (1280×720) →
  pc_camera`; `/webcam/status.index == 0`, `/pc_camera/status.index
  == 1`; `data/camera_mapping.json` written with correct fingerprints.
  Starting the Webcam feed opens index 0 (BRIO); starting the PC Cam
  feed opens index 1 (built-in). **Resolved.**

### Bilingual UI — language switcher (English default / Turkish second)
- Replaced the earlier simultaneous EN+TR rendering with a real
  one-at-a-time language switcher in the top bar.
- `frontend/src/lib/i18n.ts` — typed `{ en, tr }` dictionary covering
  brand, groups, top-bar, sidebar scope, nav, footer, switcher.
- `frontend/src/lib/i18n-context.tsx` — `LanguageProvider` with
  `useLang` / `useSetLang` / `useT` hooks and `localStorage` persistence
  (`karabuk-fwi.lang`). Sets `<html lang>` on change.
- `frontend/src/components/providers.tsx` — mounts the provider in
  `app/layout.tsx`.
- `frontend/src/components/layout/language-switcher.tsx` — segmented
  EN / TR toggle rendered in the top bar.
- `nav-items.ts` simplified: id + group + icon only; labels resolve
  from `t.nav[id]`.
- Sidebar, top bar, page headers, footer now render in one language at
  a time. Verified in preview: EN→TR and TR→EN both toggle title,
  eyebrow, nav items, descriptions, chips, footer, and persist.
- Obsolete `components/ui/bilingual.tsx` removed.
- `tsc --noEmit` clean; browser preview verified.

---


---

## Completed

### Phase 1 — ML Core (DONE)
- 34-feature deduplicated schema locked
- Stage 1 regression: HistGBR, walk-forward OOF, R² ≈ 0.819 on 2025 holdout
- Stage 2 classifier: RandomForest on OOF + 3 support features
  (`rh`, `ws`, `fuel_drying_rate`)
- Stacked decision rule: regression-centred with grey-zone rescue
- Three-way comparison validated (stacked beats parallel: 6 vs. 8 missed
  high-risk days on the 2025 holdout)
- 38 Phase 1 tests passing

### Phase 2 — Backend / API (DONE)
- Open-Meteo fetch layer (model input + soil moisture + live display)
- `StackedPredictor` inference class
- Live inference orchestrator (fetch → features → predict → persist)
- Drone logic (separate operational layer, read from latest op run)
- SQLite persistence (`run_history`, `system_state`)
- API services layer (risk, weather, history, scheduler, model)
- FastAPI application with the full operational endpoint set
- APScheduler pinned to `Europe/Istanbul` with 11:00 and 15:00 jobs
- Monitoring/detection layer (MJPEG feeds + YOLO detector) **structurally
  separated** from the prediction pipeline
- Run-type taxonomy (`OPERATIONAL_RUN_TYPES` vs. `EVALUATION_RUN_TYPES`)
  enforced at the DB boundary

### Phase 3 — Frontend Foundation (DONE)
- Next.js 16 + TypeScript + Tailwind CSS + shadcn/ui + Recharts + Lucide
- Typed API client with complete coverage of the backend endpoint set
- All timestamps displayed in Europe/Istanbul (TRT)
- Enterprise design system (`ent-card`, `ent-eyebrow`, `ent-kpi-value`,
  `ent-status-dot`, `font-display`, `font-mono-ent`, token-driven colours)
- 8 tabs: Overview → Impact & Context → Risk Decision → Features →
  Analytics → Run History → Monitoring → System
- Mobile shell (sidebar drawer) + global `ErrorBoundary`
- Live weather strictly display-only, fully isolated from model input

### Operational fixes (DONE)
- Timezone end-to-end fix: every persisted and displayed timestamp is now
  a tz-aware Istanbul ISO 8601 string, centralised in
  `src/api/time_utils.py`. APScheduler, `live_inference.py`, drone logic,
  `system_state`, notifications, `/system/health` all funnel through the
  same helper.
- One-shot DB migration (`scripts/migrate_run_timestamps_to_istanbul.py`)
  rewrote 3 legacy naive-UTC rows into Istanbul-aware ISO.
- Features/Audit experience: DB-layer `_hydrate_run_row` parses the four
  JSON payload columns (`raw_inputs_json`, `feature_values_json`,
  `validation_json`, `thresholds_json`) into object counterparts on read,
  applied uniformly to `get_latest_run`, `get_run_by_id`, and
  `get_run_history` (list stays lean). Features tab now renders the full
  34-feature audit package for the latest operational run.
- Features tab educational layer: every raw and engineered feature has a
  one-sentence explanation and (for engineered features) the exact
  generation rule copied from `src/features/build_features.py`.

### Phase 4 — Frontend UX polish & demo readiness (DONE)
- **Shared `ErrorAlert`** component (`src/components/ui/error-alert.tsx`)
  standardises every API failure surface — styled panel, destructive
  accent, icon, optional Retry button. Every tab now uses it.
- **`system-model.tsx` rewrite.** This was the last tab still using stock
  shadcn `Card` primitives, `text-green-600` / `text-red-600` hex colours,
  `font-mono` (non-enterprise), and plain "Loading..." / "Backend
  unreachable" text. It now uses `ent-card`, `ent-eyebrow`, the status-dot
  pattern, `Skeleton` loading states, `ErrorAlert` failure states, and a
  dedicated `ThresholdTile` / `ModelCard` / `MetricsTable` breakdown.
- **`risk-decision.tsx`** — manual-check error is now rendered through
  `ErrorAlert` (compact variant) instead of small inline red text, and a
  second `ErrorAlert` surfaces failures on `/risk/latest`.
- **`run-history.tsx`** — adds an explicit error branch with retry and a
  `Skeleton` row placeholder for first load; empty state copy clarified.
- **Consistency pass** — every remaining tab already conforms to the
  enterprise design system (`live-overview`, `impact-context`,
  `risk-decision`, `features-inputs`, `historical-analytics`,
  `run-history`, `monitoring-drone`).

### Phase 5 — Performance, responsiveness & camera clarity (DONE)
- **Manual risk check latency**: the dominant cost (~28 s) was a per-day
  soil-moisture HTTP loop in ``fetch_weather.build_history_window``. It
  now issues a single ``fetch_daily_soil_moisture_range`` call per
  segment (archive + forecast). Open-Meteo HTTP timeouts tightened from
  60 s → 15 s so interactive calls fail fast instead of hanging.
- **Cold-start prewarm**: ``api/main.py`` now launches two daemon threads
  at lifespan startup — one loads the stacked predictor (Stage 1 + Stage
  2) and one loads the YOLO fire detector. Neither blocks startup. The
  first manual risk check and first camera frame no longer pay their
  cold-load cost inline.
- **Camera feed redesign**: ``cameras.py`` and ``drone.py`` were split
  into two threads each — a pure I/O capture loop and a separate YOLO
  inference loop running every Nth frame (``MONITORING_INFERENCE_STRIDE``,
  default 3). MJPEG generators now yield the latest annotated frame
  without ever blocking on inference. Start feels instant instead of
  freezing for several seconds on the first YOLO pass.
- **DSHOW backend**: camera capture uses ``CAP_DSHOW`` on Windows with a
  fallback to the default backend — device probe time dropped from
  ~1–3 s to ~200 ms. Per-feed capture/inference FPS are reported through
  ``/monitoring/cameras/{id}/status`` and ``/monitoring/drone/status``
  and rendered as a chip on the Monitoring tab.
- **Structured camera errors**: ``state.last_error`` is now a
  ``{code, message}`` dict (``device_not_found`` / ``opencv_missing``
  / …), so the UI can render precise copy.
- **Camera mapping clarity — the BRIO 100 is the official project
  webcam**: the registry locks the logical IDs to physical intent
  (``pc_camera`` = built-in laptop camera, ``webcam`` = Logitech BRIO
  100). Defaults assume the most common Windows enumeration
  (``pc_camera`` → 0, ``webcam`` → 1) and three runtime tools let the
  operator correct it without a restart:
    * ``POST /monitoring/cameras/devices`` probes indices 0–3, reports
      each device's resolution + opened state + which logical camera it
      is currently assigned to.
    * ``POST /monitoring/cameras/auto-detect`` picks the
      highest-resolution opened index (BRIO reports 1920×1080 on DSHOW)
      and assigns it to ``webcam``; the next opened index goes to
      ``pc_camera``. The single-device branch tells the operator to
      plug in the missing device instead of silently collapsing both
      logical cameras to the same index.
    * ``POST /monitoring/cameras/{cam_id}/remap?new_index=N`` swaps in
      place — if another logical camera already holds that index, it
      gets the old index automatically so the operator can fix a wrong
      mapping in one click.
- **Stale-frame fix**: ``stop_camera`` and the capture-loop ``finally``
  now clear ``state.frame`` and ``state.detections`` so the MJPEG
  thumbnail cannot keep showing the last captured image after Stop.
- **Monitoring UI**: the Devices Detected strip grew an **Auto-detect**
  button (``Wand2`` icon), a per-row **Webcam / PC Cam** assign pair,
  a "likely BRIO" badge for devices reporting ≥ 1920 width, and a
  short auto-detect status message. The card label for the Webcam feed
  is ``Logitech BRIO 100``; the PC Camera feed card labels
  ``Built-in Laptop Camera``.

### Phase 6 — Product / presentation refinement (DONE)
- **User-facing naming swept to "Stacked v3".** Footer, layout metadata,
  Features / Risk / Monitoring / Impact / System cards all read "Stacked
  v3". Remaining three internal `Option 3` references in source
  comments (api.ts, detection-alerts.tsx, monitoring-drone.tsx) updated
  for documentation consistency. Internal training / test names
  (`OPTION_3_*`, `OPTION3_*` identifiers in the Python stack) are
  **unchanged**.
- **Impact & Context — Long-Range View deepened.** The block now shows
  four cited reference points (2008–2020 baseline, 2021 record, 2023
  northward shift, 2025 Karabük) with per-card burned-area chips, plus a
  new "Karabük — Structural exposure" row of four published facts
  (forest cover %, fire-season window, dominant fuel species, regional
  climate trend). Every figure carries a per-card source line. A
  `Curated · static · cited` badge is rendered so the static nature is
  obvious at a glance.
- **Features tab — Formula is now its own column.** The Raw API Inputs,
  Engineered Features and Stage 2 Meta-Features tables all render
  `Feature · Meaning · Formula · Unit · Value`. Raw inputs table hides
  the Formula column (raw API inputs have no formula). Wording swept
  from "tomorrow" framing to "operational target date" throughout.
- **New tab — `System Flow`** (`src/components/tabs/system-flow.tsx`).
  Ten-stage left-rail timeline (Fetch → Preprocess → Engineer → Predict
  → Classify → Decide → Operate → Monitor → Audit → Surface) plus a
  parallel-layers section (Monitoring & Detection, Audit & History) and
  an Operational Invariants grid. Static content, no API calls.
  Registered in `nav-items.ts` (group `System`, id `flow`) and
  `app-shell.tsx` (with its own `ErrorBoundary`).
- **Chosen title — "System Flow".** Reasons: (1) it is neutral and
  technical — appropriate for a System group sibling of System / Model;
  (2) it precisely describes what the tab shows (the flow of a single
  risk call through the pipeline); (3) it avoids the over-familiar
  "How It Works" phrasing which tends to read as a marketing page
  rather than an operator walkthrough.
- **Monitoring tab** reviewed. Structure is already correct
  (Policy strip → Devices Detected → Live Feeds grid → Notifications)
  and consistent with the enterprise design system after Phase 5; left
  as-is. Only internal `Option 3` → `Stacked v3` comment update applied.
- **Frontend `tsc --noEmit` clean** after the refinement pass.

### Documentation
- `RUN_PROJECT.md` — local run instructions, scheduler verification,
  manual check, tests, monitoring, endpoint table.
- `CORE_IDEA.md` — theoretical idea (why not canonical FWI runtime, why
  Option 3, safety-first rationale) and technical architecture
  (Karabük scope, Stage 1/2, decision rule, separation layers,
  operational invariants).
- `SQLITE_GUIDE.md` — DB location + `KARABUK_DB_PATH` override, schema,
  write path, hydrated read paths, inspection snippets, operational-only
  filter, Istanbul timestamp contract, reset procedure.

---

## Test suite
- **77 backend tests passing** (`pytest tests/ -q`)
- **Frontend `tsc --noEmit` clean** (zero TypeScript errors)

---

## How to run

### Backend
```bash
# from the project root
python backend/scripts/serve.py
# API: http://localhost:8000  |  Docs: http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm run dev
# Dashboard: http://localhost:3000
```

### Tests
```bash
# from the project root
python -m pytest backend/tests -v
```

Full runbook in [`RUN_PROJECT.md`](./RUN_PROJECT.md).
