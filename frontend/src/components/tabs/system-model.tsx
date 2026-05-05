"use client";

import { Brain, Clock, Database, Server, Shield, Sliders } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ErrorAlert } from "@/components/ui/error-alert";
import { Skeleton } from "@/components/ui/skeleton";
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
 * System & Model — operator-facing view of backend health, model
 * metadata, decision thresholds and the APScheduler state.
 *
 * Phase 4 rewrite: this tab was the last piece of the UI still using
 * stock shadcn `Card` primitives and raw Tailwind colour utilities.
 * Every surface now uses the enterprise `ent-card`/eyebrow pattern,
 * `var(--…)` tokens, `font-mono-ent` for numeric/monospace cells, and
 * `ErrorAlert` / `Skeleton` for the failure and loading states.
 *
 * Data bindings are unchanged — this is purely a visual normalisation.
 */
export function SystemModel() {
  const health = useApi(() => api.getHealth(), [], 30_000);
  const model = useApi(() => api.getModelInfo(), []);
  const scheduler = useApi(() => api.getScheduler(), [], 30_000);

  const h = health.data;
  const m = model.data;
  const s = scheduler.data;

  return (
    <div className="space-y-6">
      {/* ---------- Summary ---------- */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
          <div>
            <p className="ent-eyebrow">System / Model</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Brain
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              Daily Risk Model
            </h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
              The model uses daily aggregate weather features. Scheduled
              checks refresh the daily risk decision.
            </p>
          </div>
          <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
            Daily Inputs
          </Badge>
        </div>

        {model.error && !m ? (
          <ErrorAlert
            title="Could not load model summary"
            message={model.error}
            onRetry={model.refetch}
            compact
          />
        ) : model.loading && !m ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-20" />
            ))}
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <SummaryInfo label="Model Type" value={m?.stage1_model ?? "Stacked v3"} />
            <SummaryInfo label="Risk Target" value="FWI >= 35" />
            <SummaryInfo label="Input Type" value="Daily Aggregates" />
            <SummaryInfo
              label="Feature Count"
              value={m ? String(m.n_training_features) : "—"}
              mono
            />
            <SummaryInfo
              label="Decision Threshold"
              value={m ? String(m.thresholds.high_threshold) : "35"}
              mono
            />
            <SummaryInfo
              label="Runtime Checks"
              value={h ? `${h.stage1_model_loaded && h.stage2_model_loaded ? "Models OK" : "Model check"} · ${h.database_ok ? "DB OK" : "DB check"}` : "—"}
            />
            <SummaryInfo
              label="Training/Runtime Alignment"
              value={h?.stage1_model_loaded && h.stage2_model_loaded && h.database_ok ? "Ready" : "Check"}
              mono
            />
          </div>
        )}
      </div>

      {/* ---------- Health ---------- */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
          <div>
            <p className="ent-eyebrow">Runtime</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Server
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              System Health
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Live status of Stage 1, Stage 2 and the SQLite audit log.
              Auto-refreshes every 30 seconds.
            </p>
          </div>
          {h && (
            <Badge
              variant={h.status === "healthy" ? "default" : "destructive"}
              className="text-[10px] uppercase tracking-wider self-start md:self-center"
            >
              <span
                aria-hidden
                className="ent-status-dot mr-1.5"
                style={{
                  background:
                    h.status === "healthy"
                      ? "var(--success)"
                      : "var(--destructive)",
                }}
              />
              {h.status}
            </Badge>
          )}
        </div>

        {health.error && !h ? (
          <ErrorAlert
            title="Backend unreachable"
            message={health.error}
            onRetry={health.refetch}
          />
        ) : h ? (
          <>
            <div className="grid sm:grid-cols-3 gap-3">
              <HealthItem label="Stage 1 model" ok={h.stage1_model_loaded} />
              <HealthItem label="Stage 2 model" ok={h.stage2_model_loaded} />
              <HealthItem label="Audit database" ok={h.database_ok} />
            </div>
            <p className="text-[11px] text-muted-foreground mt-4 flex items-center gap-1.5">
              <Clock className="h-3 w-3" aria-hidden />
              Checked{" "}
              <span className="font-mono-ent text-foreground">
                {formatIstanbulTime(h.timestamp)}
              </span>
            </p>
          </>
        ) : (
          <div className="grid sm:grid-cols-3 gap-3">
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
          </div>
        )}
      </div>

      {/* ---------- Model metadata ---------- */}
      <div className="grid md:grid-cols-2 gap-6">
        <ModelCard
          eyebrow="Stage 1"
          title="Regression backbone"
          icon={<Brain className="h-4 w-4" style={{ color: "var(--primary)" }} />}
          loading={model.loading}
          error={model.error}
          onRetry={model.refetch}
        >
          {m && (
            <>
              <MetaLine label="Model" value={m.stage1_model} />
              <MetaLine
                label="Training features"
                value={String(m.n_training_features)}
              />
              {m.stage1_test_metrics && (
                <MetricsTable metrics={m.stage1_test_metrics} />
              )}
            </>
          )}
        </ModelCard>

        <ModelCard
          eyebrow="Stage 2"
          title="Safety classifier"
          icon={
            <Shield
              className="h-4 w-4"
              style={{ color: "var(--secondary)" }}
            />
          }
          loading={model.loading}
          error={model.error}
          onRetry={model.refetch}
        >
          {m && (
            <>
              <MetaLine label="Model" value={m.stage2_model} />
              <MetaLine
                label="Stage 2 input"
                value={m.stage2_input_features.join(", ")}
                mono
              />
              {m.stage2_test_metrics && (
                <MetricsTable metrics={m.stage2_test_metrics} />
              )}
            </>
          )}
        </ModelCard>
      </div>

      {/* ---------- Thresholds ---------- */}
      <div className="ent-card p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="ent-eyebrow">Decision rule</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Sliders
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              Thresholds
            </h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
              The Stacked v3 rule promotes a day to HIGH_RISK when Stage 1 is
              above the high threshold, or when Stage 1 lies in the grey
              zone and Stage 2&apos;s probability clears the rescue bar.
            </p>
          </div>
          <Badge
            variant="outline"
            className="text-[10px] uppercase tracking-wider"
          >
            Static
          </Badge>
        </div>

        {m ? (
          <div className="grid sm:grid-cols-3 gap-3">
            <ThresholdTile
              label="High threshold (FWI)"
              value={m.thresholds.high_threshold}
              hint="Stage 1 ≥ this ⇒ HIGH_RISK"
            />
            <ThresholdTile
              label="Near threshold (FWI)"
              value={m.thresholds.near_threshold}
              hint="Stage 1 in [near, high) ⇒ grey zone"
            />
            <ThresholdTile
              label="Probability threshold"
              value={m.thresholds.probability_threshold}
              hint="Stage 2 ≥ this in grey zone ⇒ rescue"
            />
          </div>
        ) : model.error ? (
          <ErrorAlert
            title="Could not load thresholds"
            message={model.error}
            onRetry={model.refetch}
            compact
          />
        ) : (
          <div className="grid sm:grid-cols-3 gap-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        )}
      </div>

      {/* ---------- Feature groups ---------- */}
      <div className="ent-card p-5">
        <div className="mb-4">
          <p className="ent-eyebrow">Features</p>
          <h3 className="font-display text-lg font-semibold leading-none mt-1">
            Model Input Groups
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Compact view of the daily aggregate inputs used by the runtime
            prediction path.
          </p>
        </div>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {[
            ...FEATURE_GROUPS,
            stage2FeatureGroup(m?.stage2_input_features),
          ].map((group) => (
            <FeatureGroupCard key={group.title} {...group} />
          ))}
        </div>
      </div>

      {/* ---------- Scheduler ---------- */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
          <div>
            <p className="ent-eyebrow">APScheduler</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Database
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              Scheduler Status
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Scheduled operational checks at 09:00, 11:00 and 15:00
              Europe/Istanbul. Jobs are registered at backend startup.
            </p>
          </div>
          {s && (
            <Badge
              variant={s.running ? "default" : "secondary"}
              className="text-[10px] uppercase tracking-wider self-start md:self-center"
            >
              <span
                aria-hidden
                className="ent-status-dot mr-1.5"
                style={{
                  background: s.running
                    ? "var(--success)"
                    : "var(--muted-foreground)",
                }}
              />
              {s.running ? "Active" : "Inactive"}
            </Badge>
          )}
        </div>

        {scheduler.error && !s ? (
          <ErrorAlert
            title="Could not read scheduler status"
            message={scheduler.error}
            onRetry={scheduler.refetch}
          />
        ) : s ? (
          s.jobs.length > 0 ? (
            <div
              className="rounded-md border overflow-hidden"
              style={{ borderColor: "var(--border)" }}
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job</TableHead>
                    <TableHead className="text-right">Next run</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {s.jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell className="text-sm">{job.name}</TableCell>
                      <TableCell className="text-right font-mono-ent text-sm">
                        {job.next_run_time
                          ? formatIstanbulTime(job.next_run_time)
                          : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Scheduler is running but no jobs are registered.
            </p>
          )
        ) : (
          <div className="space-y-2">
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- helpers ---------------------------------------------------------

const FEATURE_GROUPS = [
  {
    title: "Weather Inputs",
    features: [
      {
        name: "temperature",
        meaning: "Daily max air temperature",
        source: "temperature_2m_max",
      },
      {
        name: "rh",
        meaning: "Daily minimum humidity",
        source: "relative_humidity_2m_min",
      },
      {
        name: "ws",
        meaning: "Daily max wind speed",
        source: "wind_speed_10m_max",
      },
      {
        name: "precip",
        meaning: "Daily precipitation total",
        source: "precipitation_sum",
      },
    ],
  },
  {
    title: "Seasonal Features",
    features: [
      {
        name: "month",
        meaning: "Calendar season signal",
        source: "target date month",
      },
      {
        name: "day_of_year",
        meaning: "Annual progression signal",
        source: "target date ordinal",
      },
      {
        name: "season",
        meaning: "Fire season context",
        source: "derived from month",
      },
    ],
  },
  {
    title: "Fire Weather Features",
    features: [
      {
        name: "vpd",
        meaning: "Atmospheric drying pressure",
        source: "es x (1 - RH/100)",
      },
      {
        name: "hdw",
        meaning: "Heat-dry-wind index",
        source: "vpd x wind",
      },
      {
        name: "fuel_drying_rate",
        meaning: "Drying tendency estimate",
        source: "temp x (100 - RH)",
      },
      {
        name: "wind_squared",
        meaning: "Wind intensity effect",
        source: "ws^2",
      },
      {
        name: "dew_point",
        meaning: "Moisture condensation point",
        source: "derived from temp/RH",
      },
    ],
  },
  {
    title: "Rolling History",
    features: [
      {
        name: "precip_sum_7d",
        meaning: "Weekly rain accumulation",
        source: "rolling 7-day precip sum",
      },
      {
        name: "t_mean_7d",
        meaning: "Weekly temperature mean",
        source: "rolling 7-day temp mean",
      },
      {
        name: "rh_min_7d",
        meaning: "Weekly dry humidity",
        source: "rolling 7-day RH min",
      },
      {
        name: "ws_max_7d",
        meaning: "Weekly peak wind",
        source: "rolling 7-day wind max",
      },
    ],
  },
  {
    title: "Stage 1 Regression",
    features: [
      {
        name: "model_features",
        meaning: "Main FWI predictors",
        source: "daily weather + engineered features",
      },
      {
        name: "validation_flags",
        meaning: "Input quality checks",
        source: "runtime feature validation",
      },
    ],
  },
] as const;

function stage2FeatureGroup(features?: readonly string[]) {
  const values =
    features && features.length > 0
      ? features
      : ["predicted_fwi", "near_threshold_flag"];
  return {
    title: "Stage 2 Classifier Support",
    features: values.map((feature) => ({
      name: feature,
      meaning: stage2Meaning(feature),
      source: stage2Source(feature),
    })),
  };
}

function stage2Meaning(feature: string): string {
  if (feature.includes("prob")) return "Classifier confidence input";
  if (feature.includes("threshold")) return "Decision boundary support";
  if (feature.includes("fwi")) return "Stage 1 FWI estimate";
  return "Classifier support feature";
}

function stage2Source(feature: string): string {
  if (feature.includes("fwi")) return "Stage 1 output";
  if (feature.includes("threshold")) return "decision thresholds";
  return "engineered runtime feature";
}

function SummaryInfo({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div
      className="rounded-md border px-4 py-3"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <p className="ent-eyebrow">{label}</p>
      <p
        className={`mt-2 truncate text-sm font-medium ${mono ? "font-mono-ent" : ""}`}
        title={value}
      >
        {value}
      </p>
    </div>
  );
}

function FeatureGroupCard({
  title,
  features,
}: {
  title: string;
  features: readonly {
    name: string;
    meaning: string;
    source: string;
  }[];
}) {
  return (
    <div
      className="rounded-md border px-4 py-3"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <p className="font-medium text-sm">{title}</p>
      <div className="mt-3 space-y-2">
        {features.map((feature) => (
          <div
            key={feature.name}
            className="grid grid-cols-[minmax(7rem,0.9fr)_minmax(8rem,1.1fr)] gap-x-3 gap-y-0.5 text-xs"
          >
            <span className="font-mono-ent text-foreground truncate" title={feature.name}>
              {feature.name}
            </span>
            <span className="text-muted-foreground">{feature.meaning}</span>
            <span className="col-span-2 text-[11px] text-muted-foreground/80 truncate" title={feature.source}>
              {feature.source}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HealthItem({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div
      className="flex items-center gap-2 rounded-md border px-3 py-2"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <span
        aria-hidden
        className="ent-status-dot"
        style={{
          background: ok ? "var(--success)" : "var(--destructive)",
        }}
      />
      <span className="text-sm">{label}</span>
      <span
        className="ml-auto text-[10px] uppercase tracking-wider font-medium"
        style={{
          color: ok ? "var(--success)" : "var(--destructive)",
        }}
      >
        {ok ? "OK" : "Down"}
      </span>
    </div>
  );
}

function MetaLine({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span
        className={`text-right break-words ${mono ? "font-mono-ent" : "font-medium"}`}
      >
        {value}
      </span>
    </div>
  );
}

function MetricsTable({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div
      className="mt-3 rounded-md border overflow-hidden"
      style={{ borderColor: "var(--border)" }}
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">Metric</TableHead>
            <TableHead className="text-right text-xs">Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(metrics).map(([k, v]) => (
            <TableRow key={k}>
              <TableCell className="font-mono-ent text-xs">
                {k.toUpperCase()}
              </TableCell>
              <TableCell className="text-right font-mono-ent text-xs">
                {typeof v === "number"
                  ? Number.isInteger(v)
                    ? v
                    : v.toFixed(3)
                  : v}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ModelCard({
  eyebrow,
  title,
  icon,
  loading,
  error,
  onRetry,
  children,
}: {
  eyebrow: string;
  title: string;
  icon: React.ReactNode;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="ent-card p-5">
      <div className="mb-4">
        <p className="ent-eyebrow">{eyebrow}</p>
        <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
          {icon}
          {title}
        </h3>
      </div>
      {error ? (
        <ErrorAlert
          title="Could not load model metadata"
          message={error}
          onRetry={onRetry}
          compact
        />
      ) : loading ? (
        <div className="space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : (
        <div className="space-y-2">{children}</div>
      )}
    </div>
  );
}

function ThresholdTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint: string;
}) {
  return (
    <div
      className="rounded-md border px-4 py-3"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <p className="ent-eyebrow">{label}</p>
      <p className="font-display text-3xl font-semibold mt-1 font-mono-ent">
        {value}
      </p>
      <p className="text-[11px] text-muted-foreground mt-1">{hint}</p>
    </div>
  );
}
