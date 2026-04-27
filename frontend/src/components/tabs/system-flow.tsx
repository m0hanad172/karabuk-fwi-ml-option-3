"use client";

import {
  Activity,
  ArrowDown,
  Bell,
  Cctv,
  ClipboardList,
  Cloud,
  Database,
  Gauge,
  History,
  Layers,
  LayoutDashboard,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/**
 * System Flow — end-to-end operator walkthrough.
 *
 * Static, content-only tab. Reads nothing from the API. Its job is to
 * answer one question for a demo audience: "what actually happens when an
 * operator presses Manual Check, and where does every number come from?"
 *
 * Layout: a left-rail timeline of numbered stages. Each stage is a card
 * with a short lede, 2–4 bullets, and a small chip strip describing its
 * inputs/outputs. Monitoring and Audit are shown as strictly parallel
 * branches so the separation is visually obvious — they never write into
 * the prediction path.
 */
export function SystemFlow() {
  return (
    <div className="space-y-8">
      <HeaderCard />

      <section aria-labelledby="flow-pipeline-title" className="space-y-3">
        <SectionHeading
          id="flow-pipeline-title"
          eyebrow="Prediction path"
          title="Operational pipeline — every step a manual or scheduled run takes"
          description="Executes end-to-end in roughly 2–4 seconds. Nothing in the pipeline consumes live monitoring data or live display weather."
        />
        <Timeline stages={PIPELINE_STAGES} />
      </section>

      <section aria-labelledby="flow-parallel-title" className="space-y-3">
        <SectionHeading
          id="flow-parallel-title"
          eyebrow="Parallel layers"
          title="What runs alongside the pipeline, strictly separated"
          description="These layers never influence the predicted FWI or the drone launch policy. They are observation and audit surfaces only."
        />
        <div className="grid gap-4 md:grid-cols-2">
          <ParallelCard
            icon={Cctv}
            title="Monitoring & detection"
            eyebrow="Detection layer"
            color="var(--secondary)"
            body={
              <>
                MJPEG feeds from the drone, the Logitech BRIO 100 webcam and
                the built-in laptop camera run YOLO fire detection in a
                dedicated inference thread. Detections are saved as
                append-only snapshots in{" "}
                <code className="font-mono-ent">
                  data/notifications/alerts.jsonl
                </code>
                .
              </>
            }
            bullets={[
              "Never writes to run_history.",
              "Never modifies predicted_fwi or the drone policy.",
              "Surfaces on the Monitoring tab and the Detection Alerts evidence log.",
            ]}
          />
          <ParallelCard
            icon={History}
            title="Audit & history"
            eyebrow="Audit trail"
            color="var(--primary)"
            body={
              <>
                Every operational run writes a full audit package into
                SQLite — raw API inputs, engineered features, Stage&nbsp;1
                prediction, Stage&nbsp;2 probability, final decision, and
                the exact thresholds used. The Features and Run History
                tabs read this package back verbatim.
              </>
            }
            bullets={[
              "Only manual / scheduled runs count as operational.",
              "Every timestamp is tz-aware Istanbul ISO 8601.",
              "Test and evaluation runs are filtered out of operator-facing views.",
            ]}
          />
        </div>
      </section>

      <InvariantsCard />
    </div>
  );
}

// ---------- header ---------------------------------------------------------

function HeaderCard() {
  return (
    <section className="ent-card p-6 md:p-7">
      <p className="ent-eyebrow">System · end-to-end</p>
      <h2 className="font-display text-2xl md:text-3xl font-semibold leading-tight mt-1 flex items-center gap-2">
        <Workflow className="h-6 w-6" style={{ color: "var(--primary)" }} />
        How a Karabük fire-risk decision is produced
      </h2>
      <p className="mt-3 text-sm text-muted-foreground max-w-3xl leading-relaxed">
        A walkthrough of the full operational path — from the moment
        Open-Meteo is queried to the moment the dashboard shows a risk
        verdict. Ten stages, one strictly-separated monitoring branch, and
        one audit trail. All times Europe/Istanbul (TRT).
      </p>
      <div className="mt-5 grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatChip label="Scope" value="Karabük province" />
        <StatChip label="Schedule" value="11:00 · 15:00 TRT" />
        <StatChip label="Model" value="Stacked v3" />
        <StatChip label="Typical run time" value="~2–4 s" />
      </div>
    </section>
  );
}

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="rounded-md border px-3 py-2"
      style={{ borderColor: "var(--border)", background: "var(--muted)" }}
    >
      <p className="ent-eyebrow">{label}</p>
      <p className="font-display text-sm font-semibold leading-tight mt-0.5">
        {value}
      </p>
    </div>
  );
}

// ---------- timeline ------------------------------------------------------

interface Stage {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  lede: string;
  bullets: string[];
  inputs: string;
  outputs: string;
  tone: "primary" | "secondary" | "neutral";
}

const PIPELINE_STAGES: Stage[] = [
  {
    icon: Cloud,
    eyebrow: "Stage 1 · Fetch",
    title: "Data fetching from Open-Meteo",
    lede: "A single HTTPS call pulls ~40 days of daily aggregates plus the soil-moisture layer, all anchored to Karabük (41.20°N, 32.63°E).",
    bullets: [
      "Daily aggregates: temperature, humidity, wind, precipitation, cloud cover, shortwave radiation, evapotranspiration.",
      "Soil moisture (0–7 cm) is fetched in a single range call — one HTTP round-trip, not one-per-day.",
      "Timeouts are tight (15 s) so a slow call fails fast instead of hanging the operator.",
    ],
    inputs: "Karabük lat/lon + target date",
    outputs: "Raw daily frame (~40 rows × 8 cols)",
    tone: "primary",
  },
  {
    icon: Database,
    eyebrow: "Stage 2 · Preprocess",
    title: "Type-safe frame assembly",
    lede: "The raw payload is aligned into a per-day frame indexed by Istanbul-local dates, with a hard schema check before anything downstream touches it.",
    bullets: [
      "Column names, dtypes and units are verified against feature_schema.py.",
      "Any NaN in a required raw column short-circuits the pipeline with a structured error.",
      "Only archive + forecast segments are kept — duplicate days collapse deterministically.",
    ],
    inputs: "Raw daily frame",
    outputs: "Validated 8-col raw frame",
    tone: "primary",
  },
  {
    icon: Sparkles,
    eyebrow: "Stage 3 · Engineer",
    title: "Feature engineering (26 engineered + 8 raw = 34)",
    lede: "Builds the full feature package for the operational target date. Every rolling window uses past days only — the target day is never peeked at.",
    bullets: [
      "Seasonal encoding: sin/cos of day-of-year and month.",
      "Derived weather: VPD, HDW, fuel_drying_rate, wind², dew_point.",
      "Rolling memory (3 d / 7 d / 30 d): precip sums, temperature / RH / wind means and extremes.",
      "EWMA memory: T (α=0.3), RH (α=0.5), precip (α=0.7).",
      "Dryness counter: streak of consecutive rain-free days ending yesterday.",
    ],
    inputs: "Validated raw frame",
    outputs: "34-feature vector",
    tone: "primary",
  },
  {
    icon: Gauge,
    eyebrow: "Stage 4 · Predict",
    title: "Stage 1 regression (HistGradientBoostingRegressor)",
    lede: "The regression backbone produces a continuous predicted FWI for the target date from all 34 features.",
    bullets: [
      "Trained walk-forward on 2015–2024; 2025 held out for honest validation.",
      "OOF R² ≈ 0.819 on the 2025 holdout.",
      "This value is the primary decision signal and also one of Stage 2's four meta-features.",
    ],
    inputs: "34-feature vector",
    outputs: "predicted_fwi (float)",
    tone: "primary",
  },
  {
    icon: ShieldCheck,
    eyebrow: "Stage 5 · Classify",
    title: "Stage 2 safety classifier (RandomForest)",
    lede: "A binary classifier sees exactly 4 inputs and outputs a probability of high-risk. Its job is to rescue grey-zone days that regression alone might under-weight.",
    bullets: [
      "Inputs: predicted_fwi + rh + ws + fuel_drying_rate.",
      "Trained on OOF regressions from Stage 1 — no target-day leakage possible.",
      "Calibrated on the same 2015–2024 walk-forward split as Stage 1.",
    ],
    inputs: "4-dim meta-feature vector",
    outputs: "p_high_risk (0–1)",
    tone: "primary",
  },
  {
    icon: ClipboardList,
    eyebrow: "Stage 6 · Decide",
    title: "Stacked decision rule",
    lede: "Regression-centred rule with a classifier grey-zone rescue. Easier to reason about than a pure voting ensemble.",
    bullets: [
      "HIGH_RISK if predicted_fwi ≥ high_threshold.",
      "Otherwise HIGH_RISK if predicted_fwi is in the grey zone AND p_high_risk ≥ rescue_threshold.",
      "Else LOW_RISK. Thresholds are locked in configs/thresholds.json and surfaced on System / Model.",
    ],
    inputs: "predicted_fwi + p_high_risk + thresholds",
    outputs: "{decision, reason_code}",
    tone: "primary",
  },
  {
    icon: Activity,
    eyebrow: "Stage 7 · Operate",
    title: "Operational runs (manual + scheduled)",
    lede: "Two slots per day at 11:00 and 15:00 Europe/Istanbul; manual runs from the Risk Decision tab use the same pipeline.",
    bullets: [
      "APScheduler is pinned to Europe/Istanbul at process start — both slots are always visible on the Scheduler card.",
      "Manual and scheduled runs share identical feature building and identical thresholds.",
      "Only run_type ∈ { manual, scheduled } can surface on Overview or drive the drone policy.",
    ],
    inputs: "Decision package",
    outputs: "Operational run record",
    tone: "primary",
  },
  {
    icon: Cctv,
    eyebrow: "Stage 8 · Monitor",
    title: "Detection layer (parallel, not a pipeline step)",
    lede: "Drone and camera feeds run YOLO in a dedicated inference thread. Separation from the prediction pipeline is structural, not a convention.",
    bullets: [
      "MJPEG capture and YOLO inference run on separate threads — one cannot block the other.",
      "Detections write to a dedicated append-only JSONL alert log plus JPEG snapshots.",
      "No path from here writes predicted_fwi, run_history, or the drone policy.",
    ],
    inputs: "Camera feeds",
    outputs: "alerts.jsonl + JPEG snapshots",
    tone: "secondary",
  },
  {
    icon: History,
    eyebrow: "Stage 9 · Audit",
    title: "Run history & audit trail",
    lede: "Every operational run is persisted with its full decision package so any past call can be reconstructed bit-for-bit.",
    bullets: [
      "SQLite: run_history row with raw_inputs_json, feature_values_json, validation_json, thresholds_json.",
      "Hydrated on read so the frontend just consumes plain objects.",
      "system_state mirrors the latest operational run so /risk/latest is O(1).",
    ],
    inputs: "Operational run record",
    outputs: "Persisted audit row",
    tone: "neutral",
  },
  {
    icon: LayoutDashboard,
    eyebrow: "Stage 10 · Surface",
    title: "Dashboard — what the operator sees",
    lede: "Eight tabs map 1-to-1 to the layers above. Live display weather is rendered only on Overview and is never used as model input.",
    bullets: [
      "Overview: latest risk verdict, next run, drone policy.",
      "Risk Decision + Features: Stage 1 / Stage 2 / feature-level audit of the latest run.",
      "Analytics + Run History: historical trends and the operational audit log.",
      "Monitoring + Detection Alerts: the detection layer and its evidence log.",
    ],
    inputs: "APIs + persisted runs",
    outputs: "Operator-facing UI",
    tone: "primary",
  },
];

function Timeline({ stages }: { stages: Stage[] }) {
  return (
    <ol className="relative pl-8 md:pl-10 space-y-3">
      <div
        aria-hidden
        className="absolute left-3 md:left-4 top-2 bottom-2 w-px"
        style={{ background: "var(--border)" }}
      />
      {stages.map((s, idx) => (
        <li key={s.title} className="relative">
          <span
            aria-hidden
            className="absolute -left-[22px] md:-left-[26px] top-4 flex h-6 w-6 items-center justify-center rounded-full border font-mono-ent text-[10px] font-semibold"
            style={{
              borderColor: toneBorder(s.tone),
              background: toneTint(s.tone),
              color: toneAccent(s.tone),
            }}
          >
            {idx + 1}
          </span>
          <StageCard stage={s} />
        </li>
      ))}
    </ol>
  );
}

function StageCard({ stage }: { stage: Stage }) {
  const Icon = stage.icon;
  const accent = toneAccent(stage.tone);
  return (
    <article
      className="ent-card p-5"
      aria-label={`${stage.eyebrow}: ${stage.title}`}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="flex h-9 w-9 items-center justify-center rounded-md border shrink-0"
          style={{
            borderColor: "var(--border)",
            background: toneTint(stage.tone),
            color: accent,
          }}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="ent-eyebrow">{stage.eyebrow}</p>
          <h3 className="font-display text-base font-semibold leading-snug mt-0.5">
            {stage.title}
          </h3>
          <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
            {stage.lede}
          </p>
          <ul className="mt-3 space-y-1.5 text-[12px] text-muted-foreground leading-snug">
            {stage.bullets.map((b) => (
              <li key={b} className="flex gap-2">
                <span
                  aria-hidden
                  className="mt-[6px] h-1 w-1 rounded-full shrink-0"
                  style={{ background: accent }}
                />
                <span>{b}</span>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px]">
            <IOChip label="Input" value={stage.inputs} accent={accent} />
            <ArrowDown
              className="h-3 w-3 rotate-[-90deg] text-muted-foreground"
              aria-hidden
            />
            <IOChip label="Output" value={stage.outputs} accent={accent} />
          </div>
        </div>
      </div>
    </article>
  );
}

function IOChip({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5"
      style={{ borderColor: "var(--border)", background: "var(--muted)" }}
    >
      <span
        className="text-[9px] uppercase tracking-wider"
        style={{ color: accent }}
      >
        {label}
      </span>
      <span className="font-mono-ent text-[11px]">{value}</span>
    </span>
  );
}

// ---------- parallel cards -------------------------------------------------

function ParallelCard({
  icon: Icon,
  eyebrow,
  title,
  body,
  bullets,
  color,
}: {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  body: ReactNode;
  bullets: string[];
  color: string;
}) {
  return (
    <article className="ent-card p-5 relative overflow-hidden">
      <div
        aria-hidden
        className="absolute left-0 top-0 bottom-0 w-0.5"
        style={{ background: color }}
      />
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="flex h-9 w-9 items-center justify-center rounded-md border shrink-0"
          style={{
            borderColor: "var(--border)",
            background: "var(--muted)",
            color,
          }}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="ent-eyebrow">{eyebrow}</p>
          <h3 className="font-display text-base font-semibold leading-snug mt-0.5">
            {title}
          </h3>
          <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
            {body}
          </p>
          <ul className="mt-3 space-y-1.5 text-[12px] text-muted-foreground leading-snug">
            {bullets.map((b) => (
              <li key={b} className="flex gap-2">
                <span
                  aria-hidden
                  className="mt-[6px] h-1 w-1 rounded-full shrink-0"
                  style={{ background: color }}
                />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </article>
  );
}

// ---------- invariants -----------------------------------------------------

const INVARIANTS: { title: string; body: string }[] = [
  {
    title: "Two operational slots per day",
    body: "11:00 and 15:00 Europe/Istanbul — always both visible on the Scheduler card.",
  },
  {
    title: "Only operational runs influence the dashboard",
    body: "Test and evaluation runs never surface on Overview or change the drone policy.",
  },
  {
    title: "Istanbul time everywhere",
    body: "Every timestamp crossing the API is tz-aware Istanbul ISO 8601 from src/api/time_utils.py.",
  },
  {
    title: "Prediction and detection do not share writes",
    body: "The detection layer does not write to run_history or system_state.",
  },
  {
    title: "Live display weather is display-only",
    body: "It is never used as model input — the model always fetches its own fresh data.",
  },
];

function InvariantsCard() {
  return (
    <section className="ent-card p-5" aria-labelledby="flow-invariants-title">
      <div className="flex items-center gap-2 mb-4">
        <Bell
          className="h-4 w-4"
          style={{ color: "var(--secondary)" }}
        />
        <div>
          <p className="ent-eyebrow">Operational invariants</p>
          <h3
            id="flow-invariants-title"
            className="font-display text-lg font-semibold leading-none mt-1"
          >
            The contracts every future change must preserve
          </h3>
        </div>
      </div>
      <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {INVARIANTS.map((i) => (
          <li
            key={i.title}
            className="rounded-md border p-3"
            style={{
              borderColor: "var(--border)",
              background: "var(--muted)",
            }}
          >
            <p className="font-display font-semibold text-[13px] leading-snug flex items-center gap-1.5">
              <Layers
                className="h-3 w-3"
                style={{ color: "var(--primary)" }}
                aria-hidden
              />
              {i.title}
            </p>
            <p className="text-[11px] text-muted-foreground mt-1 leading-snug">
              {i.body}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------- section heading ------------------------------------------------

function SectionHeading({
  id,
  eyebrow,
  title,
  description,
}: {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div>
      <p className="ent-eyebrow">{eyebrow}</p>
      <h2
        id={id}
        className="font-display text-xl font-semibold leading-tight mt-0.5"
      >
        {title}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground max-w-3xl">
        {description}
      </p>
    </div>
  );
}

// ---------- tone helpers ---------------------------------------------------

function toneAccent(tone: Stage["tone"]): string {
  switch (tone) {
    case "secondary":
      return "var(--secondary)";
    case "neutral":
      return "var(--muted-foreground)";
    default:
      return "var(--primary)";
  }
}

function toneTint(tone: Stage["tone"]): string {
  switch (tone) {
    case "secondary":
      return "rgba(255, 95, 3, 0.10)";
    case "neutral":
      return "var(--muted)";
    default:
      return "rgba(7, 44, 44, 0.08)";
  }
}

function toneBorder(tone: Stage["tone"]): string {
  switch (tone) {
    case "secondary":
      return "rgba(255, 95, 3, 0.45)";
    case "neutral":
      return "var(--border)";
    default:
      return "rgba(7, 44, 44, 0.35)";
  }
}
