"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cloud,
  CloudRain,
  Droplets,
  MapPin,
  RefreshCw,
  Thermometer,
  Wind,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatIstanbulTime } from "@/lib/time";

/**
 * Overview — executive operational summary.
 *
 * Visual language is the enterprise design system (deep teal primary,
 * orange accent, Oswald display headings, Ubuntu body). Data bindings,
 * refresh intervals and Istanbul timezone formatting are unchanged.
 */
export function LiveOverview() {
  const weather = useApi(() => api.getLiveWeather(), [], 300_000);
  const latest = useApi(() => api.getLatestPrediction(), [], 60_000);
  const scheduler = useApi(() => api.getScheduler(), [], 60_000);

  const w = weather.data;
  const p = latest.data;
  const isHighRisk = p?.high_risk_flag === 1;

  return (
    <div className="space-y-6">
      {/* Alert banner */}
      <AlertBanner
        ready={!!p}
        highRisk={isHighRisk}
        predictedFwi={p?.predicted_fwi}
        runTimestamp={p?.run_timestamp}
        error={latest.error}
      />

      {/* KPI strip */}
      <section aria-label="Latest operational result">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiTile
            eyebrow="Predicted FWI"
            value={p ? p.predicted_fwi.toFixed(1) : "—"}
            caption={thresholdCaption(p?.predicted_fwi)}
            tone={kpiTone(isHighRisk)}
            loading={!p && !latest.error}
          />
          <KpiTile
            eyebrow="High Risk Probability"
            value={p ? `${(p.high_risk_probability * 100).toFixed(1)}%` : "—"}
            caption={
              p ? `Stage 2 classifier confidence` : "Stage 2 classifier"
            }
            tone={kpiTone(
              (p?.high_risk_probability ?? 0) >= 0.5 || isHighRisk,
            )}
            loading={!p && !latest.error}
          />
          <KpiTile
            eyebrow="Decision"
            value={p ? (isHighRisk ? "HIGH RISK" : "NORMAL") : "—"}
            caption={p?.decision_reason ?? "Awaiting first run"}
            tone={isHighRisk ? "danger" : p ? "success" : "neutral"}
            loading={!p && !latest.error}
          />
          <KpiTile
            eyebrow="Last Operational Run"
            value={p ? formatIstanbulTime(p.run_timestamp) : "—"}
            caption={
              p
                ? `${runTypeLabel(p.run_type)} · target ${p.target_date}`
                : "No operational runs yet"
            }
            tone="neutral"
            loading={!p && !latest.error}
          />
        </div>
      </section>

      {/* Weather + scheduler row */}
      <section className="grid lg:grid-cols-3 gap-4">
        <WeatherPanel
          loading={weather.loading}
          error={weather.error}
          source={w?.source}
          sourceTime={w?.source_time ?? null}
          fetchTime={w?.fetch_time}
          items={[
            {
              icon: <Thermometer className="h-4 w-4" />,
              label: "Temperature",
              value: w?.temperature_now,
              unit: "°C",
            },
            {
              icon: <Droplets className="h-4 w-4" />,
              label: "Humidity",
              value: w?.rh_now,
              unit: "%",
            },
            {
              icon: <Wind className="h-4 w-4" />,
              label: "Wind",
              value: w?.ws_now,
              unit: "km/h",
            },
            {
              icon: <CloudRain className="h-4 w-4" />,
              label: "Precipitation",
              value: w?.precip_now,
              unit: "mm",
            },
            {
              icon: <Cloud className="h-4 w-4" />,
              label: "Cloud Cover",
              value: w?.cloud_cover_now,
              unit: "%",
            },
          ]}
        />

        <SchedulerPanel
          running={scheduler.data?.running}
          jobs={scheduler.data?.jobs ?? []}
          loading={!scheduler.data && !scheduler.error}
          error={scheduler.error}
        />
      </section>
    </div>
  );
}

// ---------- Building blocks -------------------------------------------------

function AlertBanner({
  ready,
  highRisk,
  predictedFwi,
  runTimestamp,
  error,
}: {
  ready: boolean;
  highRisk: boolean;
  predictedFwi: number | undefined;
  runTimestamp: string | undefined;
  error: string | null;
}) {
  if (error) {
    return (
      <div
        role="status"
        className="ent-card px-5 py-4 flex items-center gap-3"
        style={{ borderColor: "var(--border)" }}
      >
        <AlertTriangle className="h-5 w-5" style={{ color: "var(--warning)" }} />
        <div className="text-sm">
          <p className="font-medium">No operational predictions yet</p>
          <p className="text-muted-foreground">
            Trigger a manual run from Risk Decision, or wait for the next
            scheduled run (11:00 / 15:00 Istanbul).
          </p>
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="ent-card px-5 py-4">
        <Skeleton className="h-5 w-2/3" />
      </div>
    );
  }

  const tone = highRisk ? "danger" : "success";
  return (
    <div
      role="alert"
      className="ent-card px-5 md:px-6 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3"
      style={{
        borderColor: toneBorder(tone),
        background: toneBg(tone),
      }}
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="flex h-9 w-9 items-center justify-center rounded-md"
          style={{ background: toneAccent(tone), color: "#FFFFFF" }}
        >
          {highRisk ? (
            <AlertTriangle className="h-5 w-5" />
          ) : (
            <CheckCircle2 className="h-5 w-5" />
          )}
        </span>
        <div>
          <p className="font-display text-base font-semibold leading-tight">
            {highRisk
              ? "HIGH RISK — Fire danger elevated"
              : "Normal conditions — No elevated risk"}
          </p>
          <p className="text-sm text-muted-foreground">
            Predicted FWI{" "}
            <span className="font-mono-ent font-medium text-foreground">
              {predictedFwi?.toFixed(1)}
            </span>{" "}
            · last run{" "}
            <span className="font-mono-ent text-foreground">
              {runTimestamp ? formatIstanbulTime(runTimestamp) : "—"}
            </span>
          </p>
        </div>
      </div>
      <Badge
        variant={highRisk ? "destructive" : "secondary"}
        className="self-start md:self-center text-[11px] uppercase tracking-wider"
      >
        {highRisk ? "Alert Active" : "All Clear"}
      </Badge>
    </div>
  );
}

type KpiTone = "neutral" | "success" | "warning" | "danger";

function KpiTile({
  eyebrow,
  value,
  caption,
  tone,
  loading,
}: {
  eyebrow: string;
  value: string;
  caption: string;
  tone: KpiTone;
  loading?: boolean;
}) {
  return (
    <div className="ent-card px-5 py-5 flex flex-col justify-between min-h-[128px]">
      <div className="flex items-center gap-2 justify-between">
        <p className="ent-eyebrow">{eyebrow}</p>
        <span
          aria-hidden
          className="ent-status-dot"
          style={{ background: toneAccent(tone) }}
        />
      </div>
      {loading ? (
        <Skeleton className="h-8 w-24 mt-3" />
      ) : (
        <p className="ent-kpi-value font-mono-ent mt-2">{value}</p>
      )}
      <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
        {caption}
      </p>
    </div>
  );
}

function WeatherPanel({
  loading,
  error,
  source,
  sourceTime,
  fetchTime,
  items,
}: {
  loading: boolean;
  error: string | null;
  source?: string;
  sourceTime: string | null;
  fetchTime?: string;
  items: {
    icon: React.ReactNode;
    label: string;
    value: number | null | undefined;
    unit: string;
  }[];
}) {
  return (
    <div className="ent-card p-5 lg:col-span-2">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="ent-eyebrow">Live Weather</p>
          <h3 className="font-display text-lg font-semibold leading-none mt-1">
            Current Conditions
          </h3>
        </div>
        <Badge
          variant="outline"
          className="text-[10px] uppercase tracking-wider border-dashed"
        >
          Display Only
        </Badge>
      </div>

      {error ? (
        <p className="text-sm text-muted-foreground">
          Weather unavailable: {error}
        </p>
      ) : loading ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-md" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {items.map((it) => (
            <WeatherMetric key={it.label} {...it} />
          ))}
        </div>
      )}

      <div className="mt-4 pt-4 border-t flex flex-col md:flex-row md:items-center md:justify-between gap-1 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <MapPin className="h-3 w-3" />
          Karabük, Turkey · source{" "}
          <span className="font-mono-ent text-foreground">{source ?? "—"}</span>
        </span>
        <span>
          Source time{" "}
          <span className="font-mono-ent text-foreground">
            {sourceTime ? formatIstanbulTime(sourceTime) : "—"}
          </span>{" "}
          · fetched{" "}
          <span className="font-mono-ent text-foreground">
            {fetchTime ? formatIstanbulTime(fetchTime) : "—"}
          </span>
        </span>
      </div>
    </div>
  );
}

function WeatherMetric({
  icon,
  label,
  value,
  unit,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | null | undefined;
  unit: string;
}) {
  return (
    <div
      className="rounded-md border px-3 py-3 flex flex-col gap-1"
      style={{ borderColor: "var(--border)", background: "var(--muted)" }}
    >
      <span
        className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide"
        style={{ color: "var(--primary)" }}
      >
        <span aria-hidden>{icon}</span>
        {label}
      </span>
      <span className="font-mono-ent text-lg font-semibold leading-none">
        {value != null ? `${value}${unit}` : "—"}
      </span>
    </div>
  );
}

function SchedulerPanel({
  running,
  jobs,
  loading,
  error,
}: {
  running: boolean | undefined;
  jobs: { id: string; name: string; next_run_time: string | null }[];
  loading: boolean;
  error: string | null;
}) {
  return (
    <div className="ent-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="ent-eyebrow">Scheduler</p>
          <h3 className="font-display text-lg font-semibold leading-none mt-1">
            Operational Runs
          </h3>
        </div>
        {running != null && (
          <Badge
            variant={running ? "default" : "secondary"}
            className="text-[10px] uppercase tracking-wider"
          >
            <span
              aria-hidden
              className="ent-status-dot mr-1.5"
              style={{
                background: running ? "var(--success)" : "var(--muted-foreground)",
              }}
            />
            {running ? "Running" : "Stopped"}
          </Badge>
        )}
      </div>

      {error ? (
        <p className="text-sm text-muted-foreground">Scheduler unavailable</p>
      ) : loading ? (
        <div className="space-y-3">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-3/4" />
        </div>
      ) : jobs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No scheduled jobs.</p>
      ) : (
        <ul className="space-y-3 text-sm">
          {jobs.map((job) => (
            <li
              key={job.id}
              className="flex items-start justify-between gap-3 pb-3 border-b last:border-0 last:pb-0"
            >
              <div className="min-w-0">
                <p className="font-medium leading-tight truncate">
                  {job.name}
                </p>
                <p className="text-[11px] text-muted-foreground flex items-center gap-1 mt-0.5">
                  <Clock className="h-3 w-3" />
                  Next run
                </p>
              </div>
              <span className="font-mono-ent text-[12px] text-right whitespace-nowrap">
                {job.next_run_time
                  ? formatIstanbulTime(job.next_run_time)
                  : "—"}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div
        className="mt-4 pt-3 border-t text-[11px] text-muted-foreground flex items-center gap-1.5"
      >
        <RefreshCw className="h-3 w-3" />
        Two operational slots per day · 11:00 & 15:00 Istanbul
      </div>
    </div>
  );
}

// ---------- helpers --------------------------------------------------------

function kpiTone(high: boolean): KpiTone {
  return high ? "danger" : "success";
}

function runTypeLabel(rt: string): string {
  if (!rt) return "—";
  return rt.charAt(0).toUpperCase() + rt.slice(1);
}

function thresholdCaption(predicted?: number): string {
  if (predicted == null) return "Stage 1 regression output";
  if (predicted >= 35) return "Above high threshold (≥ 35)";
  if (predicted >= 28) return "Grey zone (28 – 35)";
  return "Below risk zone";
}

function toneAccent(tone: KpiTone): string {
  switch (tone) {
    case "danger":
      return "var(--destructive)";
    case "warning":
      return "var(--warning)";
    case "success":
      return "var(--success)";
    default:
      return "var(--primary)";
  }
}

function toneBg(tone: KpiTone): string {
  switch (tone) {
    case "danger":
      return "rgba(220, 38, 38, 0.06)";
    case "warning":
      return "rgba(217, 119, 6, 0.08)";
    case "success":
      return "rgba(22, 163, 74, 0.06)";
    default:
      return "var(--card)";
  }
}

function toneBorder(tone: KpiTone): string {
  switch (tone) {
    case "danger":
      return "rgba(220, 38, 38, 0.35)";
    case "warning":
      return "rgba(217, 119, 6, 0.35)";
    case "success":
      return "rgba(22, 163, 74, 0.35)";
    default:
      return "var(--border)";
  }
}

