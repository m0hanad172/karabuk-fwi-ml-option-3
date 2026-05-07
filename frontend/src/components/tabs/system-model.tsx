"use client";

import { ArrowRight, Brain, Layers, Shield } from "lucide-react";

/**
 * System & Model — model card and feature catalogue.
 *
 * This tab is strictly an explainer for the trained two-stage stacked
 * pipeline. All numbers (test metrics, confusion-matrix counts) come
 * from the committed model metadata at
 * `backend/models/metadata/stage{1,2}_metadata.json`. The 34 training
 * feature names come straight from
 * `backend/src/features/feature_schema.py::TRAINING_FEATURES`. No
 * feature names are invented; every formula matches
 * `backend/src/features/build_features.py`.
 *
 * Architecture note: this tab does NOT talk to the backend. It is a
 * static reference page so it never goes blank if the backend is
 * unreachable — operators that need live runtime info use Overview /
 * Run History / System Flow.
 */
export function SystemModel() {
  return (
    <div className="space-y-6">
      <SystemSummary />
      <PipelineFlow />
      <div className="grid gap-4 lg:grid-cols-2">
        <Stage1Card />
        <Stage2Card />
      </div>
      <FeatureCatalogue />
      <AlignmentNote />
    </div>
  );
}

// ---------- A. System Summary -------------------------------------------------

function SystemSummary() {
  const items: { label: string; value: string }[] = [
    { label: "Model Type", value: "Two-stage stacked system" },
    { label: "Target", value: "Daily wildfire risk / FWI" },
    { label: "Input Type", value: "Daily aggregate weather features" },
    { label: "Training Features", value: "34" },
    { label: "Runtime Checks", value: "09:00 / 11:00 / 15:00" },
    { label: "High-Risk Rule", value: "FWI ≥ 35" },
    {
      label: "Runtime Alignment",
      value: "Daily aggregates, not hourly weather",
    },
  ];
  return (
    <section className="ent-card p-5" aria-labelledby="system-summary">
      <div className="mb-4">
        <p className="ent-eyebrow">System & Model</p>
        <h3
          id="system-summary"
          className="mt-1 flex items-center gap-2 font-display text-lg font-semibold leading-none"
        >
          <Brain className="h-4 w-4" style={{ color: "var(--primary)" }} />
          Model Card
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Static reference. Runtime numbers (next scheduled check, latest
          FWI) live on the Overview tab.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-7">
        {items.map((it) => (
          <SummaryTile key={it.label} label={it.label} value={it.value} />
        ))}
      </div>
    </section>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="rounded-md border px-3 py-2"
      style={{ background: "var(--muted)", borderColor: "var(--border)" }}
    >
      <p className="ent-eyebrow leading-tight">{label}</p>
      <p className="mt-1 font-display text-sm font-semibold leading-snug">
        {value}
      </p>
    </div>
  );
}

// ---------- B. Pipeline Flow --------------------------------------------------

function PipelineFlow() {
  const stops = [
    "Daily weather features",
    "Stage 1 — Regression Backbone",
    "predicted_fwi",
    "Stage 2 — Safety Classifier",
    "high-risk probability",
    "Risk decision",
  ];
  return (
    <section className="ent-card p-5" aria-labelledby="pipeline-flow">
      <div className="mb-3">
        <p className="ent-eyebrow">Modelling Pipeline</p>
        <h3
          id="pipeline-flow"
          className="mt-1 flex items-center gap-2 font-display text-lg font-semibold leading-none"
        >
          <Layers className="h-4 w-4" style={{ color: "var(--secondary)" }} />
          From features to decision
        </h3>
      </div>
      <ol className="flex flex-col gap-2 md:flex-row md:flex-wrap md:items-center md:gap-1.5">
        {stops.map((label, idx) => (
          <li
            key={label}
            className="flex items-center gap-1.5"
            aria-label={`Step ${idx + 1}: ${label}`}
          >
            <span
              className="rounded-md border px-2.5 py-1.5 text-[11px] font-medium leading-none"
              style={{
                background: "var(--muted)",
                borderColor: "var(--border)",
              }}
            >
              {label}
            </span>
            {idx < stops.length - 1 && (
              <ArrowRight
                className="h-3 w-3 shrink-0 text-muted-foreground"
                aria-hidden
              />
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

// ---------- C/D. Stage cards --------------------------------------------------

type StageMetric = { label: string; value: string };

function Stage1Card() {
  // Source: backend/models/metadata/stage1_metadata.json (test_metrics)
  const metrics: StageMetric[] = [
    { label: "RMSE", value: "7.259" },
    { label: "MAE", value: "5.098" },
    { label: "R²", value: "0.819" },
  ];
  return (
    <StageCard
      eyebrow="Stage 1"
      title="Regression Backbone"
      icon={<Brain className="h-4 w-4" />}
      iconColor="var(--primary)"
      modelName="HistGradientBoostingRegressor"
      input="34 daily weather + engineered features"
      output="predicted_fwi (continuous daily FWI)"
      metrics={metrics}
      note="Stage 1 estimates the continuous daily FWI value."
    />
  );
}

function Stage2Card() {
  // Source: backend/models/metadata/stage2_metadata.json (test_metrics)
  const metrics: StageMetric[] = [
    { label: "Precision", value: "0.849" },
    { label: "Recall", value: "0.900" },
    { label: "F1", value: "0.874" },
    { label: "Accuracy", value: "0.929" },
    { label: "TP", value: "45" },
    { label: "FP", value: "8" },
    { label: "FN", value: "5" },
    { label: "TN", value: "126" },
  ];
  return (
    <StageCard
      eyebrow="Stage 2"
      title="Safety Classifier"
      icon={<Shield className="h-4 w-4" />}
      iconColor="var(--destructive)"
      modelName="RandomForestClassifier (stacked)"
      input="predicted_fwi + rh + ws + fuel_drying_rate"
      output="high-risk probability + high-risk decision"
      metrics={metrics}
      note="Stage 2 supports Stage 1 by converting the predicted FWI and selected support features into a high-risk probability."
    />
  );
}

function StageCard({
  eyebrow,
  title,
  icon,
  iconColor,
  modelName,
  input,
  output,
  metrics,
  note,
}: {
  eyebrow: string;
  title: string;
  icon: React.ReactNode;
  iconColor: string;
  modelName: string;
  input: string;
  output: string;
  metrics: StageMetric[];
  note: string;
}) {
  return (
    <section className="ent-card p-5" aria-labelledby={`stage-${eyebrow}`}>
      <div className="mb-3">
        <p className="ent-eyebrow">{eyebrow}</p>
        <h3
          id={`stage-${eyebrow}`}
          className="mt-1 flex items-center gap-2 font-display text-lg font-semibold leading-none"
        >
          <span style={{ color: iconColor }}>{icon}</span>
          {title}
        </h3>
      </div>
      <dl className="space-y-1.5 text-sm">
        <KV k="Model" v={modelName} mono />
        <KV k="Input" v={input} />
        <KV k="Output" v={output} />
      </dl>
      <div className="mt-4">
        <p className="ent-eyebrow mb-2">Test metrics</p>
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
          {metrics.map((m) => (
            <div
              key={m.label}
              className="rounded-md border px-2.5 py-1.5"
              style={{
                background: "var(--muted)",
                borderColor: "var(--border)",
              }}
            >
              <p className="ent-eyebrow leading-tight">{m.label}</p>
              <p className="mt-1 font-mono-ent text-sm font-semibold leading-none">
                {m.value}
              </p>
            </div>
          ))}
        </div>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        {note}
      </p>
    </section>
  );
}

function KV({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2">
      <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {k}
      </dt>
      <dd className={mono ? "font-mono-ent text-sm" : "text-sm"}>{v}</dd>
    </div>
  );
}

// ---------- E. Feature catalogue ----------------------------------------------

type Feat = { name: string; meaning: string; source: string };

// Real names from backend/src/features/feature_schema.py — never invented.
// Formulas / derivations from backend/src/features/build_features.py.
const RAW_FEATURES: Feat[] = [
  { name: "temperature", meaning: "Daily temperature", source: "Open-Meteo daily" },
  { name: "rh", meaning: "Daily relative humidity", source: "Open-Meteo daily" },
  { name: "ws", meaning: "Daily wind speed", source: "Open-Meteo daily" },
  { name: "precip", meaning: "Daily rainfall total", source: "Open-Meteo daily" },
  {
    name: "cloud_cover_mean",
    meaning: "Daily mean cloud cover",
    source: "Open-Meteo daily",
  },
  {
    name: "shortwave_radiation_sum",
    meaning: "Daily solar energy total",
    source: "Open-Meteo daily",
  },
  {
    name: "et0_fao_evapotranspiration",
    meaning: "Reference evapotranspiration",
    source: "Open-Meteo daily (FAO ET0)",
  },
  {
    name: "soil_moisture_0_to_7cm_mean",
    meaning: "Daily mean topsoil moisture",
    source: "Open-Meteo soil-moisture daily",
  },
];

const DERIVED_FEATURES: Feat[] = [
  { name: "vpd", meaning: "Atmospheric drying pressure", source: "es × (1 − rh / 100)" },
  {
    name: "fuel_drying_rate",
    meaning: "Fuel drying tendency",
    source: "temperature × (1 − rh / 100)",
  },
  { name: "hdw", meaning: "Heat-dry-wind effect", source: "vpd × ws" },
  { name: "wind_squared", meaning: "Wind energy proxy", source: "ws²" },
  { name: "dew_point", meaning: "Dew point estimate", source: "temperature − (100 − rh) / 5" },
];

const SEASONAL_FEATURES: Feat[] = [
  { name: "doy_sin", meaning: "Seasonal cycle signal", source: "sin(2π × dayofyear / 366)" },
  { name: "doy_cos", meaning: "Seasonal cycle signal", source: "cos(2π × dayofyear / 366)" },
  { name: "month_sin", meaning: "Monthly cycle signal", source: "sin(2π × month / 12)" },
  { name: "month_cos", meaning: "Monthly cycle signal", source: "cos(2π × month / 12)" },
];

const ROLLING_FEATURES: Feat[] = [
  { name: "precip_sum_3d", meaning: "3-day rainfall memory", source: "rolling sum of previous days" },
  { name: "precip_sum_7d", meaning: "Weekly rainfall memory", source: "rolling sum of previous days" },
  { name: "precip_sum_30d", meaning: "Monthly rainfall memory", source: "rolling sum of previous days" },
  { name: "t_mean_3d", meaning: "3-day temperature trend", source: "rolling mean of previous days" },
  { name: "t_mean_7d", meaning: "Weekly temperature trend", source: "rolling mean of previous days" },
  { name: "rh_min_3d", meaning: "3-day driest humidity", source: "rolling min of previous days" },
  { name: "rh_min_7d", meaning: "Weekly driest humidity", source: "rolling min of previous days" },
  { name: "rh_mean_3d", meaning: "3-day humidity trend", source: "rolling mean of previous days" },
  { name: "rh_mean_7d", meaning: "Weekly humidity trend", source: "rolling mean of previous days" },
  { name: "ws_mean_3d", meaning: "3-day wind trend", source: "rolling mean of previous days" },
  { name: "ws_mean_7d", meaning: "Weekly wind trend", source: "rolling mean of previous days" },
  { name: "ws_max_3d", meaning: "3-day peak wind", source: "rolling max of previous days" },
  { name: "ws_max_7d", meaning: "Weekly peak wind", source: "rolling max of previous days" },
  { name: "ewma_t", meaning: "Smoothed temperature memory", source: "EWMA over previous days (α = 0.3)" },
  { name: "ewma_rh", meaning: "Smoothed humidity memory", source: "EWMA over previous days (α = 0.5)" },
  { name: "ewma_precip", meaning: "Smoothed rainfall memory", source: "EWMA over previous days (α = 0.7)" },
  {
    name: "consecutive_dry_days",
    meaning: "Length of current dry streak",
    source: "consecutive days with no rain",
  },
];

const STAGE2_SUPPORT: Feat[] = [
  { name: "predicted_fwi", meaning: "Stage 1 output", source: "from Stage 1 prediction" },
  { name: "rh", meaning: "Daily relative humidity", source: "shared with Stage 1" },
  { name: "ws", meaning: "Daily wind speed", source: "shared with Stage 1" },
  { name: "fuel_drying_rate", meaning: "Fuel drying tendency", source: "shared with Stage 1" },
];

function FeatureCatalogue() {
  return (
    <section className="ent-card p-5" aria-labelledby="feature-catalogue">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="ent-eyebrow">Feature Catalogue</p>
          <h3
            id="feature-catalogue"
            className="mt-1 font-display text-lg font-semibold leading-none"
          >
            34 daily features used by Stage 1
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            8 raw API + 26 engineered. Stage 2 reuses three of them plus the
            Stage 1 output.
          </p>
        </div>
        <span
          className="rounded-md border px-2.5 py-1 text-[11px] font-mono-ent"
          style={{ background: "var(--muted)", borderColor: "var(--border)" }}
        >
          schema: feature_schema.py
        </span>
      </div>

      <div className="space-y-4">
        <FeatureGroup
          title="Daily Weather Inputs"
          subtitle="Raw API aggregates fetched at runtime."
          count={RAW_FEATURES.length}
          features={RAW_FEATURES}
        />
        <FeatureGroup
          title="Fire-Weather Derived Features"
          subtitle="Computed from the raw aggregates above."
          count={DERIVED_FEATURES.length}
          features={DERIVED_FEATURES}
        />
        <FeatureGroup
          title="Seasonal Features"
          subtitle="Sin/cos encodings of the calendar."
          count={SEASONAL_FEATURES.length}
          features={SEASONAL_FEATURES}
        />
        <FeatureGroup
          title="Rolling / Lag Features"
          subtitle="Short- and medium-term memory of weather behaviour."
          count={ROLLING_FEATURES.length}
          features={ROLLING_FEATURES}
        />
        <FeatureGroup
          title="Stage 2 Support Features"
          subtitle="Inputs the safety classifier reads, on top of Stage 1's output."
          count={STAGE2_SUPPORT.length}
          features={STAGE2_SUPPORT}
        />
      </div>
    </section>
  );
}

function FeatureGroup({
  title,
  subtitle,
  count,
  features,
}: {
  title: string;
  subtitle: string;
  count: number;
  features: Feat[];
}) {
  return (
    <div
      className="rounded-md border"
      style={{ borderColor: "var(--border)" }}
    >
      <div
        className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-2"
        style={{ borderColor: "var(--border)", background: "var(--muted)" }}
      >
        <div>
          <p className="font-display text-sm font-semibold leading-none">
            {title}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">{subtitle}</p>
        </div>
        <span
          className="rounded-md border px-2 py-0.5 text-[11px] font-mono-ent"
          style={{ background: "var(--background)", borderColor: "var(--border)" }}
        >
          {count}
        </span>
      </div>
      <ul className="divide-y" style={{ borderColor: "var(--border)" }}>
        {features.map((f) => (
          <li
            key={f.name}
            className="grid grid-cols-1 gap-x-3 gap-y-0.5 px-4 py-2 md:grid-cols-[14rem_1fr_14rem] md:items-baseline"
          >
            <code className="font-mono-ent text-[12.5px]">{f.name}</code>
            <span className="text-sm">{f.meaning}</span>
            <span className="text-[11px] text-muted-foreground md:text-right">
              {f.source}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------- Alignment note ----------------------------------------------------

function AlignmentNote() {
  return (
    <section
      className="rounded-md border px-4 py-3 text-[12.5px] leading-relaxed"
      style={{
        borderColor: "rgba(7, 44, 44, 0.22)",
        background: "rgba(7, 44, 44, 0.04)",
      }}
      role="note"
      aria-label="Training and runtime alignment note"
    >
      <p className="font-semibold">Training / runtime alignment.</p>
      <p className="mt-1 text-muted-foreground">
        Both the training CSV and the runtime feature builder use{" "}
        <strong>daily aggregate</strong> weather inputs (max
        temperature, min RH, max wind, precipitation sum, mean cloud
        cover, solar radiation sum, ET0, soil-moisture mean). The three
        scheduled checks at 09:00 / 11:00 / 15:00 refresh the same daily
        decision; they do <strong>not</strong> produce separate hourly
        FWI values.
      </p>
    </section>
  );
}
