"use client";

import { AlertTriangle, CheckCircle2, Database, Layers } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatIstanbulTime } from "@/lib/time";

/**
 * Features & Inputs — read-only audit view of the **latest operational
 * run** (manual or scheduled). It renders the full feature package the
 * pipeline actually fed to Stage 1 and Stage 2:
 *
 *  1. Raw API inputs (Open-Meteo daily aggregates + soil moisture)
 *  2. Engineered features (seasonal encoding, derived weather, rolling
 *     memory, EWMA memory, dryness counter)
 *  3. Stage 2 meta-features (the exact 4-dim input the safety classifier
 *     receives: predicted_fwi + rh + ws + fuel_drying_rate)
 *  4. Validation summary (missing / NaN features, total checked)
 *
 * Data binding: `/risk/latest`, which is hard-wired to
 * `get_latest_run(operational_only=True)` so test and evaluation runs
 * never show up here. The backend hydrates the JSON payload columns on
 * read so this component just consumes plain objects — no parsing.
 *
 * Explanations / formulas: each row carries a short, neutral description
 * plus (for engineered features) the generation rule as documented in
 * `src/features/build_features.py`. Explanations are intentionally terse
 * — they describe the ML feature, not a physical law.
 */

// Keep this list in sync with src/features/feature_schema.py::RAW_API_FEATURES.
// The backend owns the canonical list; this copy is only used client-side
// to split raw vs. engineered rows for display.
const RAW_API_FEATURES = [
  "temperature",
  "rh",
  "ws",
  "precip",
  "cloud_cover_mean",
  "shortwave_radiation_sum",
  "et0_fao_evapotranspiration",
  "soil_moisture_0_to_7cm_mean",
];

// Stage 2 receives exactly these four inputs — predicted_fwi is the OOF
// Stage 1 prediction, the other three are lifted straight from the
// engineered-feature frame. See feature_schema.STAGE2_INPUT_FEATURES.
const STAGE2_INPUT = ["predicted_fwi", "rh", "ws", "fuel_drying_rate"];

// Short, neutral explanations for each raw and engineered feature. For
// engineered features we also surface the exact generation rule (the
// formula the pipeline uses in `src/features/build_features.py`) so the
// Features tab is self-documenting.
//
// Design rules:
//  - Keep each explanation to one sentence; no marketing language.
//  - Only claim what the pipeline actually computes; do not imply any
//    physical-law precision that the ML feature does not carry.
//  - Formulas use the same variable names as the code (T, rh, ws, etc.)
//    so anyone can cross-check against build_features.py.
type FeatureDoc = {
  explanation: string;
  formula?: string;
  unit?: string;
};

const FEATURE_DOCS: Record<string, FeatureDoc> = {
  // ---- Raw API inputs ----
  temperature: {
    explanation: "How warm the air was on average during the day.",
    unit: "°C",
  },
  rh: {
    explanation:
      "Average air humidity through the day. Lower values mean drier air.",
    unit: "%",
  },
  ws: {
    explanation: "Average wind speed at 10 m above ground during the day.",
    unit: "m/s",
  },
  precip: {
    explanation: "Total rain that fell during the day.",
    unit: "mm",
  },
  cloud_cover_mean: {
    explanation:
      "How cloudy the sky was on average. 0 % means clear, 100 % means fully overcast.",
    unit: "%",
  },
  shortwave_radiation_sum: {
    explanation:
      "How much sunlight energy reached the ground during the day.",
    unit: "MJ/m²",
  },
  et0_fao_evapotranspiration: {
    explanation:
      "How much water a standard grass surface would lose that day — a proxy for how thirsty the atmosphere is.",
    unit: "mm/day",
  },
  soil_moisture_0_to_7cm_mean: {
    explanation:
      "How wet the top 7 cm of soil was on average. Higher values mean wetter ground.",
    unit: "m³/m³",
  },

  // ---- Seasonal encoding ----
  doy_sin: {
    explanation:
      "Day of the year, encoded as a smooth curve so the model knows Dec 31 is next to Jan 1.",
    formula: "sin(2π · dayofyear / 366)",
    unit: "−1 … 1",
  },
  doy_cos: {
    explanation:
      "Second half of the day-of-year encoding (the pair together makes the cycle continuous).",
    formula: "cos(2π · dayofyear / 366)",
    unit: "−1 … 1",
  },
  month_sin: {
    explanation:
      "Month of the year as a smooth curve. Same idea as doy_sin but lower resolution.",
    formula: "sin(2π · month / 12)",
    unit: "−1 … 1",
  },
  month_cos: {
    explanation: "Second half of the month-of-year smooth encoding.",
    formula: "cos(2π · month / 12)",
    unit: "−1 … 1",
  },

  // ---- Derived weather ----
  vpd: {
    explanation:
      "Vapour Pressure Deficit — how hard the air is pulling moisture out of leaves and ground fuels. High VPD = thirsty air.",
    formula: "es = 0.6108·exp(17.27·T/(T+237.3));  vpd = es·(1 − rh/100)",
    unit: "kPa",
  },
  fuel_drying_rate: {
    explanation:
      "A simple fuel-drying proxy combining temperature and dryness. Also one of the three support features the Stage 2 classifier sees.",
    formula: "T · (1 − rh/100)",
    unit: "°C-equivalent",
  },
  hdw: {
    explanation:
      "Hot-Dry-Windy index. Multiplies VPD by wind speed to highlight days that are dry AND gusty at the same time.",
    formula: "vpd · ws",
    unit: "kPa·m/s",
  },
  wind_squared: {
    explanation:
      "Wind speed squared. Gives strong-wind days extra weight compared to calm days.",
    formula: "ws²",
    unit: "(m/s)²",
  },
  dew_point: {
    explanation:
      "Approximate temperature at which the air would become fully saturated — a simple linear estimate.",
    formula: "T − (100 − rh) / 5",
    unit: "°C",
  },

  // ---- Rolling precipitation memory ----
  precip_sum_3d: {
    explanation:
      "How much rain fell over the previous 3 days. Uses only past days — never peeks at the target day.",
    formula: "sum(precip[t−3 … t−1])",
    unit: "mm",
  },
  precip_sum_7d: {
    explanation:
      "How much rain fell over the previous 7 days — short-term wetness memory.",
    formula: "sum(precip[t−7 … t−1])",
    unit: "mm",
  },
  precip_sum_30d: {
    explanation:
      "How much rain fell over the previous 30 days — longer-term wetness memory.",
    formula: "sum(precip[t−30 … t−1])",
    unit: "mm",
  },

  // ---- Rolling temperature memory ----
  t_mean_3d: {
    explanation: "Average temperature over the previous 3 days.",
    formula: "mean(T[t−3 … t−1])",
    unit: "°C",
  },
  t_mean_7d: {
    explanation: "Average temperature over the previous 7 days.",
    formula: "mean(T[t−7 … t−1])",
    unit: "°C",
  },

  // ---- Rolling humidity memory ----
  rh_min_3d: {
    explanation:
      "The lowest humidity seen in the previous 3 days — captures a recent dry spike.",
    formula: "min(rh[t−3 … t−1])",
    unit: "%",
  },
  rh_min_7d: {
    explanation:
      "The lowest humidity seen in the previous 7 days — a slower dry-spike memory.",
    formula: "min(rh[t−7 … t−1])",
    unit: "%",
  },
  rh_mean_3d: {
    explanation: "Average humidity over the previous 3 days.",
    formula: "mean(rh[t−3 … t−1])",
    unit: "%",
  },
  rh_mean_7d: {
    explanation: "Average humidity over the previous 7 days.",
    formula: "mean(rh[t−7 … t−1])",
    unit: "%",
  },

  // ---- Rolling wind memory ----
  ws_mean_3d: {
    explanation: "Average wind speed over the previous 3 days.",
    formula: "mean(ws[t−3 … t−1])",
    unit: "m/s",
  },
  ws_mean_7d: {
    explanation: "Average wind speed over the previous 7 days.",
    formula: "mean(ws[t−7 … t−1])",
    unit: "m/s",
  },
  ws_max_3d: {
    explanation:
      "The strongest daily-mean wind seen in the previous 3 days.",
    formula: "max(ws[t−3 … t−1])",
    unit: "m/s",
  },
  ws_max_7d: {
    explanation:
      "The strongest daily-mean wind seen in the previous 7 days.",
    formula: "max(ws[t−7 … t−1])",
    unit: "m/s",
  },

  // ---- EWMA memory ----
  ewma_t: {
    explanation:
      "A weighted average of recent temperatures — more weight on the most recent days than on older ones.",
    formula: "EWMA(T, α = 0.3)",
    unit: "°C",
  },
  ewma_rh: {
    explanation:
      "A weighted average of recent humidities, leaning more strongly on the last couple of days.",
    formula: "EWMA(rh, α = 0.5)",
    unit: "%",
  },
  ewma_precip: {
    explanation:
      "A weighted average of recent rainfall, heavily biased toward the most recent days.",
    formula: "EWMA(precip, α = 0.7)",
    unit: "mm",
  },

  // ---- Dryness counter ----
  consecutive_dry_days: {
    explanation:
      "How many days in a row (ending yesterday) had no rainfall. Resets to 0 as soon as a wet day appears.",
    formula: "streak of precip[t−k] ≤ 0 mm",
    unit: "days",
  },
};

function docFor(key: string): FeatureDoc | undefined {
  return FEATURE_DOCS[key];
}

export function FeaturesInputs() {
  const latest = useApi(() => api.getLatestPrediction(), [], 60_000);
  const p = latest.data;

  const features = p?.feature_values ?? {};
  const rawInputs = p?.raw_inputs ?? {};
  const validation = p?.validation;

  const rawRows = RAW_API_FEATURES.map((key) => {
    const val = (rawInputs as Record<string, unknown>)[key];
    return {
      key,
      value: formatNumeric(val),
      doc: docFor(key),
    };
  });

  const engineeredRows = Object.entries(features)
    .filter(([k]) => !RAW_API_FEATURES.includes(k))
    .map(([key, val]) => ({
      key,
      value: formatNumeric(val),
      doc: docFor(key),
    }));

  const nothingYet = !p;

  return (
    <div className="space-y-6">
      {/* Validation strip */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <p className="ent-eyebrow">Input Audit</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Database
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              Feature Validation
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Shows the exact inputs used by the latest operational run
              (manual or scheduled). Test and evaluation runs are excluded.
            </p>
          </div>
          {validation ? (
            <Badge
              variant={validation.is_valid ? "default" : "destructive"}
              className="text-[10px] uppercase tracking-wider self-start md:self-center"
            >
              <span
                aria-hidden
                className="ent-status-dot mr-1.5"
                style={{
                  background: validation.is_valid
                    ? "var(--success)"
                    : "var(--destructive)",
                }}
              />
              {validation.is_valid ? "Valid" : "Issues Found"}
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="text-[10px] uppercase tracking-wider self-start md:self-center"
            >
              No data
            </Badge>
          )}
        </div>

        {validation && !validation.is_valid && (
          <div className="mt-4 grid sm:grid-cols-2 gap-3">
            {validation.missing_features &&
              validation.missing_features.length > 0 && (
                <ValidationIssue
                  tone="danger"
                  label="Missing features"
                  items={validation.missing_features}
                />
              )}
            {validation.nan_features && validation.nan_features.length > 0 && (
              <ValidationIssue
                tone="warning"
                label="NaN features"
                items={validation.nan_features}
              />
            )}
          </div>
        )}

        {validation?.is_valid && (
          <div
            className="mt-4 flex items-center gap-2 text-xs"
            style={{ color: "var(--success)" }}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            All required inputs present, no NaNs detected
            {typeof validation.checked === "number" && (
              <>
                {" "}
                ·{" "}
                <span className="font-mono-ent text-muted-foreground">
                  {validation.checked} features checked
                </span>
              </>
            )}
            .
          </div>
        )}

        {nothingYet && (
          <p className="mt-4 text-xs text-muted-foreground">
            No operational run yet. Trigger a manual check from the Risk
            Decision tab or wait for the next scheduled slot.
          </p>
        )}
      </div>

      {/* Raw inputs */}
      <FeatureTableCard
        eyebrow="Upstream"
        title="Raw API Inputs"
        description="Fetched from Open-Meteo daily aggregates and the soil-moisture layer, and passed straight into the feature-engineering stage for the operational target date."
        rows={rawRows}
        emptyText="No raw inputs available. Run a manual check first."
        showFormula={false}
      />

      {/* Engineered features */}
      <FeatureTableCard
        eyebrow="Pipeline"
        title="Engineered Features"
        description={`${engineeredRows.length} features built for the operational target date by the feature engineering stage (rolling memory, EWMA, derived weather, seasonal encoding). Every value is computed from past days only — never peeks at the target day.`}
        rows={engineeredRows}
        emptyText="No feature data available."
        scrollable
        showFormula
      />

      {/* Stage 2 meta-features */}
      <div className="ent-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="ent-eyebrow">Classifier</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Layers
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              Stage 2 Meta-Features
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              The exact 4-dim input the safety classifier sees for the
              operational target date — Stage&nbsp;1&apos;s prediction plus
              three support features chosen by ablation.
            </p>
          </div>
          <Badge
            variant="outline"
            className="text-[10px] uppercase tracking-wider"
          >
            Stacked v3
          </Badge>
        </div>

        <div
          className="rounded-md border overflow-hidden"
          style={{ borderColor: "var(--border)" }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[11rem]">Input</TableHead>
                <TableHead>Meaning</TableHead>
                <TableHead className="w-[16rem]">Formula</TableHead>
                <TableHead className="w-[7rem]">Unit</TableHead>
                <TableHead className="text-right w-[7rem]">Value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {STAGE2_INPUT.map((key) => {
                const value =
                  key === "predicted_fwi"
                    ? formatNumeric(p?.predicted_fwi)
                    : formatNumeric(features[key]);
                const doc: FeatureDoc | undefined =
                  key === "predicted_fwi"
                    ? {
                        explanation:
                          "Stage 1's regression output for the target date — the primary decision signal.",
                        formula: "HistGBR(all 34 features)",
                        unit: "FWI index",
                      }
                    : docFor(key);
                return (
                  <TableRow key={key}>
                    <TableCell className="font-mono-ent text-sm align-top">
                      {key}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground align-top">
                      {doc?.explanation ?? "—"}
                    </TableCell>
                    <TableCell
                      className="font-mono-ent text-[11px] align-top"
                      style={{ color: "var(--primary)" }}
                    >
                      {doc?.formula ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground font-mono-ent align-top">
                      {doc?.unit ?? "—"}
                    </TableCell>
                    <TableCell className="text-right font-mono-ent text-sm align-top">
                      {value}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>

        {p && (
          <p className="text-[11px] text-muted-foreground mt-3">
            From run{" "}
            <span className="font-mono-ent text-foreground">{p.run_id}</span>{" "}
            (<span className="font-mono-ent text-foreground">{p.run_type}</span>){" "}
            at{" "}
            <span className="font-mono-ent text-foreground">
              {formatIstanbulTime(p.run_timestamp)}
            </span>
          </p>
        )}
      </div>
    </div>
  );
}

// ---------- helpers ---------------------------------------------------------

function formatNumeric(val: unknown): string {
  if (val === null || val === undefined) return "N/A";
  if (typeof val === "number") {
    if (!Number.isFinite(val)) return "N/A";
    // Keep big numbers readable and small numbers precise.
    const abs = Math.abs(val);
    if (abs >= 100) return val.toFixed(2);
    if (abs >= 1) return val.toFixed(3);
    return val.toFixed(4);
  }
  return String(val);
}

function ValidationIssue({
  tone,
  label,
  items,
}: {
  tone: "danger" | "warning";
  label: string;
  items: string[];
}) {
  const color =
    tone === "danger" ? "var(--destructive)" : "var(--warning)";
  return (
    <div
      className="rounded-md border px-3 py-2"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <p
        className="text-[11px] font-medium uppercase tracking-wide flex items-center gap-1.5"
        style={{ color }}
      >
        <AlertTriangle className="h-3 w-3" />
        {label}
      </p>
      <p className="mt-1 text-xs font-mono-ent break-words">
        {items.join(", ")}
      </p>
    </div>
  );
}

type FeatureRow = {
  key: string;
  value: string;
  doc?: FeatureDoc;
};

function FeatureTableCard({
  eyebrow,
  title,
  description,
  rows,
  emptyText,
  scrollable,
  showFormula = false,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  rows: FeatureRow[];
  emptyText: string;
  scrollable?: boolean;
  showFormula?: boolean;
}) {
  return (
    <div className="ent-card p-5">
      <div className="mb-4">
        <p className="ent-eyebrow">{eyebrow}</p>
        <h3 className="font-display text-lg font-semibold leading-none mt-1">
          {title}
        </h3>
        {description && (
          <p className="text-xs text-muted-foreground mt-1 max-w-3xl">
            {description}
          </p>
        )}
      </div>

      {rows.length > 0 ? (
        <div
          className={`rounded-md border overflow-hidden ${scrollable ? "max-h-[32rem] overflow-y-auto" : ""}`}
          style={{ borderColor: "var(--border)" }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[14rem]">Feature</TableHead>
                <TableHead>Meaning</TableHead>
                {showFormula && (
                  <TableHead className="w-[16rem]">Formula</TableHead>
                )}
                <TableHead className="w-[7rem]">Unit</TableHead>
                <TableHead className="text-right w-[7rem]">Value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.key}>
                  <TableCell className="font-mono-ent text-sm align-top">
                    {r.key}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground align-top">
                    {r.doc?.explanation ?? "—"}
                  </TableCell>
                  {showFormula && (
                    <TableCell
                      className="font-mono-ent text-[11px] align-top"
                      style={{ color: "var(--primary)" }}
                    >
                      {r.doc?.formula ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  )}
                  <TableCell className="text-xs text-muted-foreground font-mono-ent align-top">
                    {r.doc?.unit ?? "—"}
                  </TableCell>
                  <TableCell className="text-right font-mono-ent text-sm align-top">
                    {r.value}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      )}
    </div>
  );
}
