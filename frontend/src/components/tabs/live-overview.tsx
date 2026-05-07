"use client";

import { useState } from "react";
import {
  Camera,
  Clock,
  CloudRain,
  Droplets,
  Plane,
  ShieldAlert,
  Thermometer,
  Wind,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusToast, type StatusToastState } from "@/components/ui/status-toast";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatIstanbulTime } from "@/lib/time";
import { LiveFeedsPanel } from "./monitoring-drone";

export function LiveOverview() {
  const weather = useApi(() => api.getLiveWeather(), [], 300_000);
  const latest = useApi(() => api.getLatestPrediction(), [], 60_000);
  const scheduler = useApi(() => api.getScheduler(), [], 60_000);
  const cameras = useApi(() => api.listCameras(), [], 15_000);
  const droneStatus = useApi(() => api.getDroneMonitoringStatus(), [], 15_000);
  const dronePolicy = useApi(() => api.getDroneState(), [], 30_000);
  const alertSummary = useApi(() => api.getDetectionAlertsSummary(), [], 30_000);

  const w = weather.data;
  const p = latest.data;
  const isHighRisk = p?.high_risk_flag === 1;
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoToast, setDemoToast] = useState<StatusToastState | null>(null);

  async function runDemoPatrol() {
    if (
      !window.confirm(
        "Run controlled drone demo patrol? Physical launch requires operator confirmation.",
      )
    ) {
      return;
    }
    setDemoBusy(true);
    try {
      const mode = droneStatus.data?.mode === "tello" ? "tello" : "mock";
      const result = await api.runDemoPatrol(mode, true);
      setDemoToast({
        title: "Demo Patrol",
        tone: result.ok ? "success" : "warning",
        message: result.message,
      });
    } catch (e) {
      setDemoToast({
        title: "Demo Patrol",
        tone: "danger",
        message: (e as Error).message,
      });
    } finally {
      setDemoBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <StatusToast toast={demoToast} onClose={() => setDemoToast(null)} />

      <CompactTopSummary
        weatherLoading={weather.loading}
        weatherError={weather.error}
        riskLoading={!p && !latest.error}
        schedulerLoading={!scheduler.data && !scheduler.error}
        currentStatus={p ? (isHighRisk ? "High Risk" : "Normal") : "—"}
        highRisk={isHighRisk}
        predictedFwi={p?.predicted_fwi}
        probability={p?.high_risk_probability}
        updatedAt={p?.run_timestamp}
        targetDate={p?.target_date}
        nextCheck={nextScheduledCheckCompact(scheduler.data?.jobs)}
        temperature={w?.temperature_now}
        humidity={w?.rh_now}
        wind={w?.ws_now}
        precipitation={w?.precip_now}
      />

      <LiveFeedsPanel />

      <section className="grid gap-3 lg:grid-cols-3" aria-label="Secondary overview details">
        <OperationalSchedule
          running={scheduler.data?.running}
          nextCheck={nextScheduledCheck(scheduler.data?.jobs)}
          loading={!scheduler.data && !scheduler.error}
          error={scheduler.error}
        />
        <DroneReadyStrip
          active={!!dronePolicy.data?.active_alert_window}
          status={dronePolicy.data?.drone_status}
          nextLaunch={dronePolicy.data?.next_launch_time}
          reason={dronePolicy.data?.reason}
          loading={!dronePolicy.data && !dronePolicy.error}
          error={dronePolicy.error}
          onRunDemo={runDemoPatrol}
          demoBusy={demoBusy}
        />
        <MonitoringStatusPanel
          cameras={cameras.data?.cameras ?? []}
          droneRunning={!!droneStatus.data?.running}
          droneMode={droneStatus.data?.mode}
          hardwareAvailable={droneStatus.data?.hardware_available}
          loading={
            (!cameras.data && !cameras.error) ||
            (!droneStatus.data && !droneStatus.error)
          }
          error={cameras.error || droneStatus.error}
        />
        <LatestDetectionPanel
          summary={alertSummary.data ?? null}
          loading={!alertSummary.data && !alertSummary.error}
          error={alertSummary.error}
        />
      </section>
    </div>
  );
}

function CompactTopSummary({
  weatherLoading,
  weatherError,
  riskLoading,
  schedulerLoading,
  currentStatus,
  highRisk,
  predictedFwi,
  probability,
  updatedAt,
  targetDate,
  nextCheck,
  temperature,
  humidity,
  wind,
  precipitation,
}: {
  weatherLoading: boolean;
  weatherError: string | null;
  riskLoading: boolean;
  schedulerLoading: boolean;
  currentStatus: string;
  highRisk: boolean;
  predictedFwi?: number;
  probability?: number;
  updatedAt?: string;
  targetDate?: string;
  nextCheck: string;
  temperature?: number | null;
  humidity?: number | null;
  wind?: number | null;
  precipitation?: number | null;
}) {
  return (
    <section className="ent-card p-3" aria-label="Current operations summary">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <p className="ent-eyebrow">Live Monitoring</p>
          <h3 className="font-display text-base font-semibold leading-none mt-1">
            Current Status
          </h3>
        </div>
        <Badge
          variant={highRisk ? "destructive" : "secondary"}
          className="text-[10px] uppercase tracking-wider"
        >
          {currentStatus}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-12">
        <SummaryTile
          label="Status"
          value={currentStatus}
          tone={highRisk ? "danger" : "success"}
          loading={riskLoading}
          className="xl:col-span-2"
        />
        <SummaryTile
          label="Last FWI"
          value={predictedFwi != null ? predictedFwi.toFixed(1) : "—"}
          caption={updatedAt ? `Updated: ${shortDateTime(updatedAt)}` : targetDate ? `Target: ${shortDate(targetDate)}` : undefined}
          mono
          loading={riskLoading}
          className="md:col-span-2 xl:col-span-2"
        />
        <SummaryTile
          label="Probability"
          value={probability != null ? `${(probability * 100).toFixed(1)}%` : "—"}
          mono
          loading={riskLoading}
          className="xl:col-span-2"
        />
        <SummaryTile
          label="Next Check"
          value={nextCheck}
          mono
          loading={schedulerLoading}
          className="xl:col-span-2"
        />
        <ScheduledChecksTile className="md:col-span-2 xl:col-span-4" />
        <WeatherTile
          icon={<Thermometer className="h-3.5 w-3.5" />}
          label="Temperature"
          value={temperature}
          unit="°C"
          loading={weatherLoading}
          error={weatherError}
          className="xl:col-span-3"
        />
        <WeatherTile
          icon={<Droplets className="h-3.5 w-3.5" />}
          label="Humidity"
          value={humidity}
          unit="%"
          loading={weatherLoading}
          error={weatherError}
          className="xl:col-span-3"
        />
        <WeatherTile
          icon={<Wind className="h-3.5 w-3.5" />}
          label="Wind"
          value={wind}
          unit="km/h"
          loading={weatherLoading}
          error={weatherError}
          className="xl:col-span-3"
        />
        <WeatherTile
          icon={<CloudRain className="h-3.5 w-3.5" />}
          label="Precipitation"
          value={precipitation}
          unit="mm"
          loading={weatherLoading}
          error={weatherError}
          className="xl:col-span-3"
        />
      </div>
    </section>
  );
}

function SummaryTile({
  label,
  value,
  caption,
  tone = "neutral",
  mono = false,
  loading = false,
  className = "",
}: {
  label: string;
  value: string;
  caption?: string;
  tone?: "neutral" | "success" | "danger";
  mono?: boolean;
  loading?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`min-h-[76px] rounded-md border px-3 py-2 ${className}`}
      style={{
        borderColor: tone === "danger" ? "rgba(220, 38, 38, 0.35)" : "var(--border)",
        background: tone === "danger" ? "rgba(220, 38, 38, 0.06)" : "var(--muted)",
      }}
    >
      <p className="ent-eyebrow">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-5 w-20" />
      ) : (
        <p
          className={`mt-1 truncate text-base font-semibold leading-tight ${mono ? "font-mono-ent" : ""}`}
          title={value}
          style={{
            color:
              tone === "danger"
                ? "var(--destructive)"
                : tone === "success"
                  ? "var(--success)"
                  : "var(--foreground)",
          }}
        >
          {value}
        </p>
      )}
      {caption && (
        <p className="mt-0.5 text-[10px] leading-tight text-muted-foreground" title={caption}>
          {caption}
        </p>
      )}
    </div>
  );
}

function ScheduledChecksTile({ className = "" }: { className?: string }) {
  return (
    <div
      className={`min-h-[76px] rounded-md border px-3 py-2 ${className}`}
      style={{ borderColor: "var(--border)", background: "var(--muted)" }}
    >
      <p className="ent-eyebrow">Scheduled</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {["09:00", "11:00", "15:00"].map((time) => (
          <span
            key={time}
            className="rounded-sm border px-2 py-1 font-mono-ent text-[11px] font-semibold leading-none"
            style={{
              borderColor: "var(--border)",
              background: "var(--card)",
            }}
          >
            {time}
          </span>
        ))}
      </div>
    </div>
  );
}

function WeatherTile({
  icon,
  label,
  value,
  unit,
  loading,
  error,
  className = "",
}: {
  icon: React.ReactNode;
  label: string;
  value?: number | null;
  unit: string;
  loading: boolean;
  error: string | null;
  className?: string;
}) {
  return (
    <div
      className={`min-h-[76px] rounded-md border px-3 py-2 ${className}`}
      style={{ borderColor: "var(--border)", background: "var(--muted)" }}
    >
      <p className="ent-eyebrow flex items-center gap-1.5">
        <span aria-hidden style={{ color: "var(--primary)" }}>
          {icon}
        </span>
        {label}
      </p>
      {loading ? (
        <Skeleton className="mt-2 h-5 w-16" />
      ) : (
        <p className="mt-1 truncate font-mono-ent text-base font-semibold leading-tight">
          {error ? "—" : value != null ? `${value}${unit}` : "—"}
        </p>
      )}
    </div>
  );
}

function OperationalSchedule({
  running,
  nextCheck,
  loading,
  error,
}: {
  running?: boolean;
  nextCheck: string;
  loading: boolean;
  error: string | null;
}) {
  const rows = [
    ["09:00", "Early Warning Check"],
    ["11:00", "Main Operational Check"],
    ["15:00", "Afternoon Re-check"],
  ] as const;

  return (
    <div className="ent-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="ent-eyebrow">Operational Schedule</p>
          <h3 className="font-display text-sm font-semibold leading-none mt-1">
            Risk Checks
          </h3>
        </div>
        <Badge variant={running ? "default" : "secondary"} className="text-[10px] uppercase tracking-wider">
          {loading ? "Loading" : error ? "Unavailable" : running ? "Active" : "Standby"}
        </Badge>
      </div>
      <div className="space-y-2 text-sm">
        {rows.map(([time, label]) => (
          <div key={time} className="flex items-center justify-between gap-3">
            <span className="font-mono-ent text-xs font-semibold">{time}</span>
            <span className="min-w-0 flex-1 truncate text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 border-t pt-2 text-[11px] text-muted-foreground">
        Next check <span className="font-mono-ent text-foreground">{nextCheck}</span>
      </div>
    </div>
  );
}

function DroneReadyStrip({
  active,
  status,
  nextLaunch,
  reason,
  loading,
  error,
  onRunDemo,
  demoBusy,
}: {
  active: boolean;
  status?: string;
  nextLaunch?: string | null;
  reason?: string;
  loading: boolean;
  error: string | null;
  onRunDemo: () => void;
  demoBusy: boolean;
}) {
  return (
    <div className="ent-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="ent-eyebrow">Drone-ready</p>
          <h3 className="font-display text-sm font-semibold leading-none mt-1">
            Patrol Status
          </h3>
        </div>
        {loading ? (
          <Skeleton className="h-6 w-24" />
        ) : error ? (
          <Badge variant="secondary">Unavailable</Badge>
        ) : (
          <Badge variant={active ? "destructive" : "secondary"} className="text-[10px] uppercase tracking-wider">
            {active ? "Recommended" : "Standby"}
          </Badge>
        )}
      </div>
      <div className="space-y-2 text-sm">
        <SummaryLine
          icon={<Plane className="h-3.5 w-3.5" />}
          label="Mode"
          value={status ?? "Operator"}
        />
        <SummaryLine
          icon={<Clock className="h-3.5 w-3.5" />}
          label="Next patrol"
          value={nextLaunch ? formatIstanbulTime(nextLaunch) : "—"}
        />
      </div>
      {reason && (
        <p className="mt-2 truncate text-[11px] text-muted-foreground" title={reason}>
          {reason}
        </p>
      )}
      <Button
        type="button"
        size="sm"
        onClick={onRunDemo}
        disabled={demoBusy}
        className="mt-3 h-7 w-full px-3 text-[11px]"
      >
        {demoBusy ? "Running..." : "Run Demo Patrol"}
      </Button>
    </div>
  );
}

function MonitoringStatusPanel({
  cameras,
  droneRunning,
  droneMode,
  hardwareAvailable,
  loading,
  error,
}: {
  cameras: { cam_id: string; running?: boolean }[];
  droneRunning: boolean;
  droneMode?: string;
  hardwareAvailable?: boolean;
  loading: boolean;
  error: string | null;
}) {
  const runningCameras = cameras.filter((c) => c.running).length;
  const totalCameras = cameras.length || 2;
  const anyFeedLive = runningCameras > 0 || droneRunning;

  return (
    <div className="ent-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="ent-eyebrow">System Status</p>
          <h3 className="font-display text-sm font-semibold leading-none mt-1">
            Monitoring
          </h3>
        </div>
        <Badge variant={anyFeedLive ? "default" : "secondary"} className="text-[10px] uppercase tracking-wider">
          {anyFeedLive ? "Active" : "Standby"}
        </Badge>
      </div>
      {error ? (
        <p className="text-sm text-muted-foreground">Monitoring unavailable</p>
      ) : loading ? (
        <div className="space-y-2">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-2/3" />
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <SummaryLine
            icon={<Camera className="h-3.5 w-3.5" />}
            label="Cameras"
            value={`${runningCameras}/${totalCameras} live`}
          />
          <SummaryLine
            icon={<Plane className="h-3.5 w-3.5" />}
            label="Drone"
            value={
              droneRunning
                ? "Live"
                : hardwareAvailable === false
                  ? "Mock"
                  : "Standby"
            }
          />
          <SummaryLine
            icon={<ShieldAlert className="h-3.5 w-3.5" />}
            label="Mode"
            value={droneMode ? titleCase(droneMode) : "Mock"}
          />
        </div>
      )}
    </div>
  );
}

function LatestDetectionPanel({
  summary,
  loading,
  error,
}: {
  summary: {
    total: number;
    unread_count: number;
    latest_alert?: {
      source: string;
      time_str: string;
      max_confidence: number;
      detection_count: number;
    } | null;
  } | null;
  loading: boolean;
  error: string | null;
}) {
  const latest = summary?.latest_alert ?? null;

  return (
    <div className="ent-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="ent-eyebrow">Latest Alert</p>
          <h3 className="font-display text-sm font-semibold leading-none mt-1">
            Detection
          </h3>
        </div>
        <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
          {summary ? `${summary.unread_count} unread` : "SQLite"}
        </Badge>
      </div>

      {error ? (
        <p className="text-sm text-muted-foreground">Alert summary unavailable</p>
      ) : loading ? (
        <Skeleton className="h-12 w-full" />
      ) : latest ? (
        <div className="space-y-2 text-sm">
          <SummaryLine
            icon={<ShieldAlert className="h-3.5 w-3.5" />}
            label={titleCase(latest.source)}
            value={`${(latest.max_confidence * 100).toFixed(0)}%`}
          />
          <p className="text-[11px] text-muted-foreground">
            {latest.detection_count} detection
            {latest.detection_count === 1 ? "" : "s"} · {latest.time_str}
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No detection alerts yet.</p>
      )}
    </div>
  );
}

function SummaryLine({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
        <span aria-hidden style={{ color: "var(--primary)" }}>
          {icon}
        </span>
        <span className="truncate">{label}</span>
      </span>
      <span className="font-mono-ent text-xs text-right whitespace-nowrap">
        {value}
      </span>
    </div>
  );
}

function nextScheduledCheck(jobs?: { next_run_time: string | null }[]): string {
  const next = jobs
    ?.map((job) => job.next_run_time)
    .filter((value): value is string => Boolean(value))
    .sort()[0];
  return next ? formatIstanbulTime(next) : "—";
}

function nextScheduledCheckCompact(
  jobs?: { next_run_time: string | null }[],
): string {
  const next = jobs
    ?.map((job) => job.next_run_time)
    .filter((value): value is string => Boolean(value))
    .sort()[0];
  return next ? compactDateTime(next) : "—";
}

function shortDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      timeZone: "Europe/Istanbul",
    }).format(new Date(value));
  } catch {
    return value.slice(0, 10);
  }
}

function shortDateTime(value: string): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Europe/Istanbul",
    }).format(new Date(value)).replace(",", "");
  } catch {
    return value.slice(0, 16).replace("T", " ");
  }
}

function compactDateTime(value: string): string {
  if (!value || value === "—") return "—";
  try {
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Europe/Istanbul",
    }).format(new Date(value)).replace(",", "");
  } catch {
    return value;
  }
}

function titleCase(value: string): string {
  if (!value) return "—";
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
