# Phase 3 Summary — Frontend Foundation

## What Was Built

| Component | File | Purpose |
|---|---|---|
| Next.js app | `frontend/` | Next.js 16 + TypeScript + Tailwind CSS + shadcn/ui |
| API client | `frontend/src/lib/api.ts` | Typed client for all 10 backend endpoints |
| Time utilities | `frontend/src/lib/time.ts` | All timestamps formatted in Europe/Istanbul |
| Data hook | `frontend/src/hooks/use-api.ts` | Reusable fetch hook with auto-refresh support |
| Layout + navigation | `frontend/src/app/page.tsx` | 6-tab layout with header/footer |
| Tab 1: Live Overview | `frontend/src/components/tabs/live-overview.tsx` | Weather cards (display-only, 5min refresh), alert banner, latest prediction, scheduler |
| Tab 2: Risk Decision | `frontend/src/components/tabs/risk-decision.tsx` | FWI gauge, probability bar, decision badge, manual check button |
| Tab 3: Features/Inputs | `frontend/src/components/tabs/features-inputs.tsx` | Raw inputs table, engineered features, Stage 2 meta-features, validation status |
| Tab 5: Run History | `frontend/src/components/tabs/run-history.tsx` | Paginated history table with expandable detail rows |
| Tab 6: System/Model | `frontend/src/components/tabs/system-model.tsx` | Health check, model info, metrics, thresholds, scheduler status |
| Tab 7: Monitoring/Drone | `frontend/src/components/tabs/monitoring-drone.tsx` | Drone state, placeholder video feeds (disconnected/no-signal) |
| Launch config | `.claude/launch.json` | Dev server configs for backend (port 8000) and frontend (port 3000) |

---

## Fully Complete

- Next.js project scaffold with TypeScript, Tailwind, shadcn/ui
- API client with full type coverage for all backend endpoints
- Time formatting locked to Europe/Istanbul for Karabuk scope
- Tab 1 (Live Overview): weather cards, alert banner, latest prediction, scheduler info
- Tab 2 (Risk Decision): predicted FWI, probability, decision, manual check trigger
- Tab 3 (Features/Inputs): raw inputs, engineered features, Stage 2 meta-features, validation
- Tab 5 (Run History): paginated table with expandable detail view
- Tab 6 (System/Model): health status, model metadata, thresholds, scheduler
- Tab 7 (Monitoring/Drone): drone state, placeholder camera feeds with status labels
- Production build passes cleanly (`npm run build` — no errors, no type errors)

---

## Partially Complete

- **Tab 4 (Historical Analytics)**: Not yet implemented. Requires chart-based FWI trends, seasonal comparisons, and high-risk history. Recharts is installed but no chart components built yet. This tab was deferred because the backend `/history/runs` endpoint provides run-level data but not aggregated time-series suitable for trend charts. A dedicated historical data endpoint or client-side aggregation would improve this.

---

## Still Pending from Phase 3

1. **Tab 4 — Historical Analytics**: FWI trend line chart, seasonal year-over-year comparison, high-risk day distribution. Recharts is ready; needs chart components and possibly a backend endpoint for historical FWI data.
2. **Responsive polish**: Tab navigation works but may benefit from a mobile-friendly layout (e.g., dropdown or scrollable tabs on small screens).
3. **Error boundary**: Global error boundary for graceful API failure handling across tabs.
4. **Loading skeletons**: Currently using text-based loading states; could upgrade to shimmer/skeleton components for polish.

---

## Key Design Decisions

- **Live weather cards** are explicitly labeled "Display Only" with a badge and are fetched from `/weather/live` (separate from model input).
- **Manual check** triggers `POST /risk/check` with fresh model-input weather fetch — the UI explicitly states "This does NOT reuse the live display weather cards."
- **All timestamps** go through `formatIstanbulTime()` which uses `Intl.DateTimeFormat` with `timeZone: "Europe/Istanbul"`.
- **Auto-refresh intervals**: weather 5min, predictions 1min, health/scheduler 30s.
- **Drone/camera feeds** are placeholder-only with loading/disconnected/no-signal states, ready for future stream integration.
