"use client";

import {
  Bell,
  Camera,
  Cctv,
  Filter,
  FlaskConical,
  Gauge,
  Hash,
  ImageIcon,
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
import { api, apiUrl, type DetectionAlert } from "@/lib/api";

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
 *  - alerts live in `data/notifications/alerts.jsonl` (append-only)
 *  - snapshots live as JPEGs in the same directory, served via
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
export function DetectionAlerts() {
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const summary = useApi(
    () => api.getDetectionAlertsSummary(),
    [],
    15_000,
  );
  const alerts = useApi(
    () => api.listDetectionAlerts(200, 0, sourceFilter ?? undefined),
    [sourceFilter],
    15_000,
  );

  const refetchAll = useCallback(() => {
    summary.refetch();
    alerts.refetch();
    // deps intentionally omitted — refetch is stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          <span className="font-semibold">Durable evidence log.</span> Every
          fire detection ever raised by the drone, webcam and PC camera — saved
          append-only to disk with snapshots. For live feeds, see the{" "}
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
              Durable append-only log of every fire detection raised by the
              drone, webcam and PC camera feeds. Strictly separate from the
              prediction pipeline — alerts here never influence the FWI
              decision or the drone launch policy.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Demo trigger — useful when no camera/drone hardware is
                connected. Appends a synthetic alert through the same
                persistence path as a real YOLO detection so the
                Detection Alerts tab, the in-app banner, and the
                summary tiles can all be verified end-to-end. */}
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
              eyebrow="Total alerts"
              value={String(summaryData.total)}
              icon={<Hash className="h-4 w-4" />}
              accent="var(--primary)"
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
      <div className="ent-card p-4">
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
              tab to begin watching, or click <strong>Test alert</strong>{" "}
              above to append a synthetic alert and verify that the
              dashboard notification flow is wired up end-to-end.
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
                    <TableHead className="w-20">Snapshot</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Time (Istanbul)</TableHead>
                    <TableHead className="text-right">Detections</TableHead>
                    <TableHead className="text-right w-[12rem]">
                      Max confidence
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((alert) => (
                    <AlertRow
                      key={alert.id}
                      alert={alert}
                      onOpen={() => setSelectedId(alert.id)}
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
}: {
  alert: DetectionAlert;
  onOpen: () => void;
}) {
  const confidencePct = Math.max(0, Math.min(alert.max_confidence, 1));
  const accent =
    confidencePct >= 0.75
      ? "var(--destructive)"
      : confidencePct >= 0.5
        ? "var(--warning)"
        : "var(--success)";

  return (
    <TableRow
      className="cursor-pointer hover:bg-muted/50"
      onClick={onOpen}
    >
      <TableCell>
        <AlertThumb image={alert.image} label={alert.source} />
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
    </TableRow>
  );
}

function AlertThumb({
  image,
  label,
}: {
  image: string | null;
  label: string;
}) {
  if (image) {
    return (
      // Using a plain <img> here because the snapshot URLs are served by
      // the FastAPI static mount on a different origin during dev —
      // next/image would require remotePatterns config. Fine for a
      // thumbnail; alt text keeps it accessible.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={apiUrl(image)}
        alt={`${label} fire detection snapshot`}
        className="h-12 w-16 object-cover rounded border"
        style={{ borderColor: "var(--border)" }}
      />
    );
  }
  return (
    <div
      className="h-12 w-16 rounded border flex items-center justify-center"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <ImageIcon className="h-4 w-4 text-muted-foreground" aria-hidden />
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
              {alert.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={apiUrl(alert.image)}
                  alt={`Fire detection snapshot from ${sourceLabel(alert.source)} at ${alert.time_str}`}
                  className="max-h-[420px] w-auto"
                />
              ) : (
                <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground text-sm">
                  <ImageIcon className="h-6 w-6" aria-hidden />
                  No snapshot was saved for this alert.
                </div>
              )}
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
