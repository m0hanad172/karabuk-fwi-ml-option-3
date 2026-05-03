"use client";

import {
  Bell,
  Camera,
  Cctv,
  CheckCheck,
  Filter,
  FlaskConical,
  Gauge,
  Hash,
  ImageIcon,
  Mail,
  Plane,
  RefreshCw,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { api, snapshotUrl, type DetectionAlert } from "@/lib/api";

/**
 * Detection Alerts — operational evidence centre.
 *
 * This tab is strictly a read-only view of the durable fire-detection
 * evidence log (`/monitoring/alerts*`). It shares absolutely nothing
 * with the Stacked v3 prediction pipeline — no run_history writes, no
 * influence on predicted_fwi, no drone launch policy. Detection alerts
 * are a monitoring-side observation, and this tab exists only to make
 * them auditable and browsable.
 *
 * Data model recap:
 *  - alerts live in SQLite table `detection_alerts`
 *  - snapshots live as JPEGs in `data/notifications/`, served via
 *    `/static/notifications/<file>` by a FastAPI static mount
 *  - each alert carries the full per-detection list (label, confidence,
 *    bbox) so the detail drawer can render a proper evidence sheet
 *
 * UI composition:
 *  - Summary strip (total / by-source / highest confidence / last time)
 *  - Source filter pills
 *  - Alerts table with source badge, snapshot thumb, confidence bar
 *  - Click-to-open detail drawer with the full snapshot + bbox list
 */
type ReadFilter = "all" | "unread" | "read";

export function DetectionAlerts() {
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [readFilter, setReadFilter] = useState<ReadFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);

  const summary = useApi(
    () => api.getDetectionAlertsSummary(),
    [],
    15_000,
  );
  const alerts = useApi(
    () =>
      api.listDetectionAlerts(
        200,
        0,
        sourceFilter ?? undefined,
        readFilter,
      ),
    [sourceFilter, readFilter],
    15_000,
  );
  // Runtime feature flag: backend-driven, not a build-time NEXT_PUBLIC_*
  // var, so flipping BACKEND_ENV / DEMO_ALERTS_ENABLED on the running
  // backend immediately hides/shows the Test alert button without a
  // frontend rebuild.
  const runtimeConfig = useApi(() => api.getRuntimeConfig(), []);
  const demoEnabled = runtimeConfig.data?.demo_alerts_enabled ?? false;

  const refetchAll = useCallback(() => {
    summary.refetch();
    alerts.refetch();
    // deps intentionally omitted — refetch is stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const markOneRead = useCallback(
    async (id: string) => {
      try {
        await api.markDetectionAlertRead(id);
      } catch {
        // Best effort: a failed mark-as-read is not user-fatal — the
        // unread badge will still reflect server truth on next poll.
      }
      refetchAll();
    },
    [refetchAll],
  );

  const markOneUnread = useCallback(
    async (id: string) => {
      try {
        await api.markDetectionAlertUnread(id);
      } catch {
        // Best effort: the list refresh below restores server truth.
      }
      refetchAll();
    },
    [refetchAll],
  );

  const markAllRead = useCallback(async () => {
    setMarkingAll(true);
    try {
      await api.markAllDetectionAlertsRead();
    } catch {
      // see above
    }
    setMarkingAll(false);
    refetchAll();
  }, [refetchAll]);

  const rows = alerts.data?.alerts ?? [];
  const summaryData = summary.data;

  const byCount = summaryData?.by_source ?? {};
  const totalBySource = useMemo(
    () => ({
      drone: byCount.drone ?? 0,
      webcam: byCount.webcam ?? 0,
      pc_camera: byCount.pc_camera ?? 0,
    }),
    [byCount],
  );

  return (
    <div className="space-y-6">
      {/* Layer tag — makes Detection Alerts vs Monitoring unambiguous */}
      <div
        className="rounded-md border px-4 py-2.5 text-[12px] leading-snug flex items-start gap-2"
        style={{
          borderColor: "rgba(7, 44, 44, 0.22)",
          background: "rgba(7, 44, 44, 0.04)",
        }}
        role="note"
      >
        <span
          aria-hidden
          className="mt-[3px] h-2 w-2 rounded-full shrink-0"
          style={{ background: "var(--primary)" }}
        />
        <span>
          <span className="font-semibold">Alert log.</span> Every fire /
          smoke detection from CCTV, the camera feeds, and the drone
          stream — saved with a snapshot. Live feeds: see the{" "}
          <span className="font-medium">Monitoring</span> tab.
        </span>
      </div>

      {/* ---------- Summary strip ---------- */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
          <div>
            <p className="ent-eyebrow">Evidence centre</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Bell
                className="h-4 w-4"
                style={{ color: "var(--secondary)" }}
              />
              Detection Alerts
            </h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
              Every fire / smoke detection from CCTV, webcam, PC camera,
              and the drone stream lands here. Separate from the risk
              prediction pipeline.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Demo trigger: only rendered when the backend reports
                demo_alerts_enabled=true (BACKEND_ENV=development OR
                DEMO_ALERTS_ENABLED=true). Appends a synthetic alert
                through the same persistence path as a real YOLO
                detection so the Detection Alerts tab, the in-app
                banner, and the summary tiles can all be verified
                end-to-end. */}
            {demoEnabled && (
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  try {
                    await api.createTestDetectionAlert("fire", 0.78, "demo");
                    refetchAll();
                  } catch {
                    // Surfaces via the underlying summary/list error
                    // states; nothing extra to do here.
                  }
                }}
                title="Append a synthetic 'fire' alert (source=demo) for testing the dashboard."
              >
                <FlaskConical className="h-3.5 w-3.5 mr-1.5" />
                Test alert
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={refetchAll}>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              Refresh
            </Button>
          </div>
        </div>

        {summary.error && !summaryData ? (
          <ErrorAlert
            title="Could not load alert summary"
            message={summary.error}
            onRetry={summary.refetch}
          />
        ) : summaryData ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <SummaryTile
              eyebrow="Alerts"
              value={
                summaryData.unread_count > 0
                  ? `${summaryData.unread_count} unread`
                  : "All read"
              }
              caption={`of ${summaryData.total} total`}
              icon={<Hash className="h-4 w-4" />}
              accent={
                summaryData.unread_count > 0
                  ? "var(--destructive)"
                  : "var(--primary)"
              }
            />
            <SummaryTile
              eyebrow="Highest confidence"
              value={
                summaryData.max_confidence != null
                  ? `${(summaryData.max_confidence * 100).toFixed(1)}%`
                  : "—"
              }
              icon={<Gauge className="h-4 w-4" />}
              accent="var(--destructive)"
            />
            <SummaryTile
              eyebrow="Last alert"
              value={summaryData.last_time_str ?? "—"}
              caption={
                summaryData.last_source
                  ? `from ${sourceLabel(summaryData.last_source)}`
                  : undefined
              }
              icon={<Bell className="h-4 w-4" />}
              accent="var(--secondary)"
              mono
            />
            <SourceBreakdownTile
              drone={totalBySource.drone}
              webcam={totalBySource.webcam}
              pcCamera={totalBySource.pc_camera}
            />
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        )}
      </div>

      {/* ---------- Filter pills ---------- */}
      <div className="ent-card p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 mr-2">
            <Filter className="h-3 w-3" aria-hidden />
            Source
          </span>
          <FilterPill
            active={sourceFilter === null}
            onClick={() => setSourceFilter(null)}
            label="All"
            count={summaryData?.total}
          />
          <FilterPill
            active={sourceFilter === "drone"}
            onClick={() => setSourceFilter("drone")}
            label="Drone"
            count={totalBySource.drone}
            icon={<Plane className="h-3 w-3" aria-hidden />}
          />
          <FilterPill
            active={sourceFilter === "webcam"}
            onClick={() => setSourceFilter("webcam")}
            label="Webcam"
            count={totalBySource.webcam}
            icon={<Cctv className="h-3 w-3" aria-hidden />}
          />
          <FilterPill
            active={sourceFilter === "pc_camera"}
            onClick={() => setSourceFilter("pc_camera")}
            label="PC Camera"
            count={totalBySource.pc_camera}
            icon={<Camera className="h-3 w-3" aria-hidden />}
          />
        </div>
        {/* Read-state filter + bulk action. Backed by the read-state
            detection_alerts table so unread/read state survives backend
            restarts. */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5 mr-2">
            <Mail className="h-3 w-3" aria-hidden />
            Read state
          </span>
          <FilterPill
            active={readFilter === "all"}
            onClick={() => setReadFilter("all")}
            label="All"
            count={summaryData?.total}
          />
          <FilterPill
            active={readFilter === "unread"}
            onClick={() => setReadFilter("unread")}
            label="Unread"
            count={summaryData?.unread_count}
          />
          <FilterPill
            active={readFilter === "read"}
            onClick={() => setReadFilter("read")}
            label="Read"
            count={summaryData?.read_count}
          />
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            disabled={
              markingAll ||
              !summaryData ||
              summaryData.unread_count === 0
            }
            onClick={markAllRead}
            title="Mark every detection alert as read."
          >
            <CheckCheck className="h-3.5 w-3.5 mr-1.5" />
            Mark all as read
          </Button>
        </div>
      </div>

      {/* ---------- Alerts table ---------- */}
      <div className="ent-card p-5">
        <div className="mb-4">
          <p className="ent-eyebrow">Alerts</p>
          <h3 className="font-display text-lg font-semibold leading-none mt-1">
            {sourceFilter
              ? `${sourceLabel(sourceFilter)} alerts`
              : "All detection alerts"}
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            {rows.length} alert{rows.length === 1 ? "" : "s"} shown · click
            any row to open the saved snapshot and detection details.
          </p>
        </div>

        {alerts.error && rows.length === 0 ? (
          <ErrorAlert
            title="Could not load detection alerts"
            message={alerts.error}
            onRetry={alerts.refetch}
          />
        ) : alerts.loading && rows.length === 0 ? (
          <div className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : rows.length === 0 ? (
          <div
            className="rounded-md border border-dashed px-6 py-10 text-center text-sm text-muted-foreground space-y-2"
            style={{ borderColor: "var(--border)" }}
          >
            <p className="font-medium text-foreground">
              No detection alerts recorded yet.
            </p>
            <p>
              Alerts will appear here automatically when smoke or fire is
              detected. Start a drone or camera feed from the Monitoring
              tab to begin watching
              {demoEnabled ? (
                <>
                  , or click <strong>Test alert</strong> above to append a
                  synthetic alert and verify that the dashboard notification
                  flow is wired up end-to-end.
                </>
              ) : (
                "."
              )}
            </p>
          </div>
        ) : (
          <div
            className="rounded-md border overflow-hidden"
            style={{ borderColor: "var(--border)" }}
          >
            <div className="max-h-[640px] overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8" aria-label="Read state" />
                    <TableHead className="w-20">Snapshot</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Time (Istanbul)</TableHead>
                    <TableHead className="text-right">Detections</TableHead>
                    <TableHead className="text-right w-[12rem]">
                      Max confidence
                    </TableHead>
                    <TableHead className="w-10" aria-label="Mark as read" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((alert) => (
                    <AlertRow
                      key={alert.id}
                      alert={alert}
                      onOpen={() => {
                        setSelectedId(alert.id);
                      }}
                      onMarkRead={() => markOneRead(alert.id)}
                      onMarkUnread={() => markOneUnread(alert.id)}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </div>

      {/* ---------- Detail drawer ---------- */}
      {selectedId && (
        <AlertDetailDrawer
          alertId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}

// ---------- Summary tiles --------------------------------------------------

function SummaryTile({
  eyebrow,
  value,
  caption,
  icon,
  accent,
  mono,
}: {
  eyebrow: string;
  value: string;
  caption?: string;
  icon: React.ReactNode;
  accent: string;
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
      <div className="flex items-center justify-between">
        <p className="ent-eyebrow">{eyebrow}</p>
        <span aria-hidden style={{ color: accent }}>
          {icon}
        </span>
      </div>
      <p
        className={`mt-2 font-display text-2xl font-semibold leading-tight ${
          mono ? "font-mono-ent" : ""
        }`}
      >
        {value}
      </p>
      {caption && (
        <p className="text-[11px] text-muted-foreground mt-1">{caption}</p>
      )}
    </div>
  );
}

function SourceBreakdownTile({
  drone,
  webcam,
  pcCamera,
}: {
  drone: number;
  webcam: number;
  pcCamera: number;
}) {
  return (
    <div
      className="rounded-md border px-4 py-3"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <p className="ent-eyebrow">By source</p>
      <div className="mt-2 space-y-1.5 text-xs">
        <SourceLine label="Drone" count={drone} icon={<Plane className="h-3 w-3" />} />
        <SourceLine label="Webcam" count={webcam} icon={<Cctv className="h-3 w-3" />} />
        <SourceLine
          label="PC Camera"
          count={pcCamera}
          icon={<Camera className="h-3 w-3" />}
        />
      </div>
    </div>
  );
}

function SourceLine({
  label,
  count,
  icon,
}: {
  label: string;
  count: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <span style={{ color: "var(--primary)" }} aria-hidden>
        {icon}
      </span>
      <span className="flex-1">{label}</span>
      <span className="font-mono-ent text-foreground">{count}</span>
    </div>
  );
}

// ---------- Filter pill ----------------------------------------------------

function FilterPill({
  active,
  onClick,
  label,
  count,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
  icon?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors"
      style={{
        borderColor: active ? "var(--primary)" : "var(--border)",
        background: active ? "var(--primary)" : "transparent",
        color: active ? "#FFFFFF" : "var(--foreground)",
      }}
    >
      {icon}
      <span>{label}</span>
      {count != null && (
        <span
          className="font-mono-ent text-[10px] px-1.5 rounded-sm"
          style={{
            background: active
              ? "rgba(255,255,255,0.15)"
              : "var(--muted)",
            color: active ? "#FFFFFF" : "var(--muted-foreground)",
          }}
        >
          {count}
        </span>
      )}
    </button>
  );
}

// ---------- Alert row ------------------------------------------------------

function AlertRow({
  alert,
  onOpen,
  onMarkRead,
  onMarkUnread,
}: {
  alert: DetectionAlert;
  onOpen: () => void;
  onMarkRead: () => void;
  onMarkUnread: () => void;
}) {
  const confidencePct = Math.max(0, Math.min(alert.max_confidence, 1));
  const accent =
    confidencePct >= 0.75
      ? "var(--destructive)"
      : confidencePct >= 0.5
        ? "var(--warning)"
        : "var(--success)";
  const unread = !alert.read;

  return (
    <TableRow
      className={`cursor-pointer hover:bg-muted/50 ${unread ? "font-semibold" : ""}`}
      onClick={onOpen}
      style={
        unread
          ? {
              // A subtle left accent strip is a much less noisy "unread"
              // signal than a full-row tint and matches the established
              // mailbox idiom.
              boxShadow: "inset 3px 0 0 0 var(--destructive)",
            }
          : undefined
      }
    >
      <TableCell aria-label={unread ? "Unread" : "Read"}>
        <span
          aria-hidden
          className="inline-block h-2 w-2 rounded-full"
          style={{
            background: unread ? "var(--destructive)" : "transparent",
            outline: unread ? "none" : "1px solid var(--border)",
            outlineOffset: "1px",
          }}
        />
      </TableCell>
      <TableCell>
        <AlertThumb alert={alert} />
      </TableCell>
      <TableCell>
        <SourceBadge source={alert.source} />
      </TableCell>
      <TableCell className="text-sm font-mono-ent">
        {alert.time_str}
      </TableCell>
      <TableCell className="text-right font-mono-ent text-sm">
        {alert.detection_count}
      </TableCell>
      <TableCell>
        <div className="flex items-center justify-end gap-2">
          <div
            className="h-1.5 w-24 rounded-full overflow-hidden"
            style={{ background: "var(--muted)" }}
            aria-hidden
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${confidencePct * 100}%`,
                background: accent,
              }}
            />
          </div>
          <span className="font-mono-ent text-sm w-12 text-right">
            {(confidencePct * 100).toFixed(0)}%
          </span>
        </div>
      </TableCell>
      <TableCell
        // Stop propagation so clicking the icon-button doesn't also open
        // the detail drawer. The whole row stays clickable for "open".
        onClick={(e) => e.stopPropagation()}
        className="text-right"
      >
        {unread ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={onMarkRead}
            title="Mark as read"
            className="h-8 w-8 p-0"
          >
            <CheckCheck className="h-4 w-4" aria-hidden />
            <span className="sr-only">Mark as read</span>
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            onClick={onMarkUnread}
            title="Mark as unread"
            className="h-8 w-8 p-0"
          >
            <Mail className="h-4 w-4" aria-hidden />
            <span className="sr-only">Mark as unread</span>
          </Button>
        )}
      </TableCell>
    </TableRow>
  );
}

function AlertThumb({ alert }: { alert: DetectionAlert }) {
  return (
    <SnapshotImage
      alert={alert}
      className="h-12 w-16 object-cover rounded border"
      placeholderClassName="h-12 w-16 rounded border"
      compact
    />
  );
}

function SnapshotImage({
  alert,
  className,
  placeholderClassName,
  compact = false,
}: {
  alert: DetectionAlert;
  className: string;
  placeholderClassName: string;
  compact?: boolean;
}) {
  const [attempt, setAttempt] = useState(0);
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const image = alert.image;

  useEffect(() => {
    if (!image) {
      setLoadedSrc(null);
      setFailed(false);
      return;
    }

    let cancelled = false;
    setLoadedSrc(null);
    setFailed(false);
    const src = snapshotUrl(image, alert.snapshot_version, attempt);
    const img = new window.Image();
    img.onload = () => {
      if (!cancelled) setLoadedSrc(src);
    };
    img.onerror = () => {
      if (!cancelled) {
        if (attempt < 5) {
          window.setTimeout(() => {
            if (!cancelled) setAttempt((value) => value + 1);
          }, 1_200);
        } else {
          setFailed(true);
        }
      }
    };
    img.src = src;
    return () => {
      cancelled = true;
    };
  }, [image, alert.snapshot_version, attempt]);

  useEffect(() => {
    setAttempt(0);
  }, [image, alert.snapshot_version]);

  if (image && loadedSrc) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={loadedSrc}
        alt={`Fire detection snapshot from ${sourceLabel(alert.source)} at ${alert.time_str}`}
        className={className}
        style={{ borderColor: "var(--border)" }}
      />
    );
  }

  const message = !image
    ? "No snapshot"
    : failed
      ? "Snapshot unavailable"
      : "Snapshot preparing...";

  return (
    <div
      className={`${placeholderClassName} flex items-center justify-center`}
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
      title={message}
    >
      {compact ? (
        <ImageIcon className="h-4 w-4 text-muted-foreground" aria-hidden />
      ) : (
        <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground text-sm">
          <ImageIcon className="h-6 w-6" aria-hidden />
          <span>{message}</span>
        </div>
      )}
    </div>
  );
}

function SourceBadge({ source }: { source: string }) {
  const label = sourceLabel(source);
  const { icon, tone } = sourceMeta(source);
  return (
    <Badge
      variant="outline"
      className="text-[10px] uppercase tracking-wider inline-flex items-center gap-1"
      style={{
        borderColor: tone,
        color: tone,
      }}
    >
      {icon}
      {label}
    </Badge>
  );
}

function sourceLabel(source: string): string {
  switch (source) {
    case "drone":
      return "Drone";
    case "webcam":
      return "Webcam";
    case "pc_camera":
      return "PC Camera";
    default:
      return source;
  }
}

function sourceMeta(source: string): { icon: React.ReactNode; tone: string } {
  switch (source) {
    case "drone":
      return {
        icon: <Plane className="h-3 w-3" aria-hidden />,
        tone: "var(--primary)",
      };
    case "webcam":
      return {
        icon: <Cctv className="h-3 w-3" aria-hidden />,
        tone: "var(--secondary)",
      };
    case "pc_camera":
      return {
        icon: <Camera className="h-3 w-3" aria-hidden />,
        tone: "var(--warning)",
      };
    default:
      return {
        icon: <Bell className="h-3 w-3" aria-hidden />,
        tone: "var(--muted-foreground)",
      };
  }
}

// ---------- Detail drawer --------------------------------------------------

function AlertDetailDrawer({
  alertId,
  onClose,
}: {
  alertId: string;
  onClose: () => void;
}) {
  const detail = useApi(() => api.getDetectionAlert(alertId), [alertId]);
  const alert = detail.data;

  // Close on Esc.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Detection alert detail"
    >
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.55)" }}
        onClick={onClose}
      />
      <div
        className="relative z-10 w-full max-w-3xl max-h-[90vh] overflow-y-auto ent-card p-6"
        style={{ background: "var(--background)" }}
      >
        <div className="flex items-start justify-between mb-5">
          <div>
            <p className="ent-eyebrow">Detection evidence</p>
            <h3 className="font-display text-xl font-semibold leading-none mt-1">
              Alert detail
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 hover:bg-muted"
            aria-label="Close detail view"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {detail.error ? (
          <ErrorAlert
            title="Could not load alert detail"
            message={detail.error}
            onRetry={detail.refetch}
          />
        ) : detail.loading || !alert ? (
          <div className="space-y-3">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ) : (
          <div className="space-y-5">
            {/* Snapshot */}
            <div
              className="rounded-md border overflow-hidden flex items-center justify-center"
              style={{
                borderColor: "var(--border)",
                background: "var(--muted)",
                minHeight: "16rem",
              }}
            >
              <SnapshotImage
                alert={alert}
                className="max-h-[420px] w-auto"
                placeholderClassName="min-h-64 w-full"
              />
            </div>

            {/* Meta grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetaField label="Source" value={<SourceBadge source={alert.source} />} />
              <MetaField
                label="Time (Istanbul)"
                value={
                  <span className="font-mono-ent text-sm">
                    {alert.time_str}
                  </span>
                }
              />
              <MetaField
                label="Detections"
                value={
                  <span className="font-mono-ent text-sm">
                    {alert.detection_count}
                  </span>
                }
              />
              <MetaField
                label="Max confidence"
                value={
                  <span className="font-mono-ent text-sm">
                    {(alert.max_confidence * 100).toFixed(1)}%
                  </span>
                }
              />
            </div>

            {/* Detection list */}
            <div>
              <p className="ent-eyebrow mb-2">Detection list</p>
              {alert.detections.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No per-detection rows were captured for this alert.
                </p>
              ) : (
                <div
                  className="rounded-md border overflow-hidden"
                  style={{ borderColor: "var(--border)" }}
                >
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">#</TableHead>
                        <TableHead>Label</TableHead>
                        <TableHead className="text-right">
                          Confidence
                        </TableHead>
                        <TableHead className="text-right">
                          Bbox [x1, y1, x2, y2]
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {alert.detections.map((d, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="font-mono-ent text-xs">
                            {idx + 1}
                          </TableCell>
                          <TableCell className="text-sm">{d.label}</TableCell>
                          <TableCell className="text-right font-mono-ent text-sm">
                            {(d.confidence * 100).toFixed(1)}%
                          </TableCell>
                          <TableCell className="text-right font-mono-ent text-xs">
                            {d.bbox.length === 4
                              ? `[${d.bbox.map((n) => n.toFixed(0)).join(", ")}]`
                              : "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>

            <p className="text-[11px] text-muted-foreground">
              Alert id{" "}
              <span className="font-mono-ent text-foreground">
                {alert.id}
              </span>{" "}
              · durable evidence log · never writes{" "}
              <span className="font-mono-ent">run_history</span>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function MetaField({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <p className="ent-eyebrow">{label}</p>
      <div className="mt-1">{value}</div>
    </div>
  );
}
