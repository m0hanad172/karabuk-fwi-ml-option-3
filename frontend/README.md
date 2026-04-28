# Karabük FWI Dashboard (frontend)

Next.js 16 + React 19 dashboard for the Karabük FWI Wildfire Risk
Prediction system. Current tabs: Overview, Impact & Context, Risk
Decision, Features, Analytics, Run History, Monitoring, Detection
Alerts, System Info, and System Flow.

> ⚠️ This project pins **Next.js 16**. APIs and conventions differ from
> older Next versions — see [AGENTS.md](./AGENTS.md). Read
> `node_modules/next/dist/docs/` before making framework-level changes.

## Stack

- Next.js 16 (App Router) + React 19
- Tailwind CSS v4 + shadcn-style components
- Recharts for analytics
- Lucide-react icons
- Base UI primitives (`@base-ui/react`)
- TypeScript 5

## Scripts

```bash
npm install            # install deps (runs once after clone)
npm run dev            # development server at http://localhost:3000
npm run build          # production build
npm run start          # serve the production build
npm run lint           # ESLint
```

## Configuration

The frontend reads a single environment variable:

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL used by `src/lib/api.ts` |

Copy [`.env.example`](./.env.example) to `.env.local` if you need to
override it. Anything else (timezone display, polling intervals,
thresholds, demo alert availability) is sourced live from the backend
— there is no second source of truth in the frontend. The Detection
Alerts **Test alert** button is shown only when `GET /system/config`
returns `demo_alerts_enabled=true`.

## Layout

```
frontend/
├── src/
│   ├── app/                 App router entrypoint + global styles
│   ├── components/
│   │   ├── layout/          App shell, sidebar, top bar, language switcher
│   │   ├── tabs/            One file per dashboard tab
│   │   └── ui/              Reusable UI primitives (button, card, table…)
│   ├── hooks/use-api.ts     Typed fetch + polling hook
│   └── lib/
│       ├── api.ts           Backend client + response types
│       ├── i18n.ts          i18n strings + provider context
│       └── time.ts          Istanbul-aware time helpers
├── public/                  Static assets (impact hero, logos)
├── package.json
├── tsconfig.json
└── .env.example
```

## Backend dependency

The dashboard expects the FastAPI backend on the URL in
`NEXT_PUBLIC_API_URL`. Start it from the repo root:

```bash
python backend/scripts/serve.py
```

Health check: <http://localhost:8000/system/health>

If the backend is unreachable, every tab renders an `ErrorAlert` with
the underlying fetch error — that is intentional, not a frontend bug.

The official runtime is **Local Hardware Mode**: the backend runs
directly on the Windows host so OpenCV / DSHOW can reach the live
webcam, PC camera, and Tello drone. There is no Docker path in the
active workflow.

## Monitoring tab

The Monitoring tab displays backend MJPEG streams for Drone, Webcam,
and PC Camera. It does not use browser webcam permissions. The
backend runs locally so OpenCV can access the host devices through
DirectShow (Windows). When a camera index can't be opened, the tab
renders a clean unavailable state and structured `last_error` instead
of a broken stream.

## Detection Alerts tab

Detection Alerts reads from the SQLite `detection_alerts` table
through `/monitoring/alerts*`. Operators can filter All / Unread /
Read, mark one alert as read, or mark all alerts as read. Read state
is a column on the row (`is_read`, `read_at`), so refreshing the
browser or restarting the backend never resets unread counts. JPG
snapshots are referenced by `snapshot_path` and served via the
FastAPI static mount at `/static/notifications/`.

## Time / locale

All operational timestamps in the UI are rendered in
**Europe/Istanbul** via `src/lib/time.ts`. The backend always emits
tz-aware ISO 8601 strings with an explicit `+03:00` (or `+04:00`
during DST) offset.
