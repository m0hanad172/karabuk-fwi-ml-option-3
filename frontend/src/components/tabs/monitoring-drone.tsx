"use client";

import {
  AlertTriangle,
  Camera,
  HardDrive,
  Laptop,
  MonitorOff,
  Play,
  Plane,
  RefreshCw,
  ShieldAlert,
  Square,
  Trash2,
  Wand2,
  Webcam,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import {
  api,
  apiUrl,
  type CameraDevice,
  type CameraStatus,
  type DroneMonitoringStatus,
  type MonitoringRuntime,
  type MonitoringNotification,
} from "@/lib/api";
import { formatIstanbulTime } from "@/lib/time";
import { cn } from "@/lib/utils";

/**
 * Monitoring — operations-console layout.
 *
 * Phase 5: redesigned for performance, responsiveness, and camera clarity.
 *
 * Architecture is unchanged:
 *   - detection layer (/monitoring/*) is strictly separate from prediction
 *   - three REAL feeds: Drone (MJPEG) / Webcam (Logitech BRIO 100) / PC Camera
 *   - Drone Operational Policy reads /drone/state from the Stacked v3 risk path
 *   - notifications list polled every 5s from SQLite-backed alerts
 *
 * Phase 5 improvements:
 *   - Feed state reconciles against backend status before mounting MJPEG
 *   - Devices Detected strip: probes local camera indices so the operator
 *     can see which slots are physically connected + their assignments
 *   - Structured error display: device_not_found vs opencv_missing
 *   - Per-feed perf chip: capture FPS / inference FPS
 *   - Camera labels match physical devices (BRIO 100 = webcam, built-in = pc_camera)
 */
export function MonitoringDrone() {
  const dronePolicy = useApi(() => api.getDroneState(), [], 30_000);
  const notifications = useApi(
    () => api.getMonitoringNotifications(25),
    [],
    5_000,
  );

  const deleteNotification = useCallback(
    async (id: string) => {
      if (!window.confirm("Delete this alert?")) return;
      try {
        await api.deleteDetectionAlert(id);
      } catch {
        // The refresh below restores server truth if the delete failed.
      }
      notifications.refetch();
    },
    // deps intentionally omitted; refetch is stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const p = dronePolicy.data;

  return (
    <div className="space-y-6">
      {/* Layer tag — makes Monitoring vs Detection Alerts unambiguous */}
      <div
        className="rounded-md border px-4 py-2.5 text-[12px] leading-snug flex items-start gap-2"
        style={{
          borderColor: "rgba(255, 95, 3, 0.35)",
          background: "rgba(255, 95, 3, 0.06)",
        }}
        role="note"
      >
        <span
          aria-hidden
          className="mt-[3px] h-2 w-2 rounded-full shrink-0"
          style={{ background: "var(--secondary)" }}
        />
        <span>
          <span className="font-semibold">Drone-ready Prototype.</span>{" "}
          Current demo uses operator-controlled drone movement. High Risk
          prepares patrol; it does not auto-launch hardware. For the durable
          alert record, see the <span className="font-medium">Detection Alerts</span> tab.
        </span>
      </div>

      {/* Policy strip */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
          <div>
            <p className="ent-eyebrow">Operator-controlled Demo</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Plane className="h-4 w-4" style={{ color: "var(--primary)" }} />
              Drone-ready Prototype
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Physical drone launch requires operator confirmation.
            </p>
          </div>
          {p && (
            <Badge
              variant={p.active_alert_window ? "destructive" : "secondary"}
              className="text-[10px] uppercase tracking-wider self-start md:self-center"
            >
              <span
                aria-hidden
                className="ent-status-dot mr-1.5"
                style={{
                  background: p.active_alert_window
                    ? "var(--destructive)"
                    : "var(--muted-foreground)",
                }}
              />
              {p.drone_status}
            </Badge>
          )}
        </div>
        {p ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <PolicyTile
              label="Patrol Recommended"
              value={p.active_alert_window ? "Yes" : "No"}
              tone={p.active_alert_window ? "danger" : "neutral"}
            />
            <PolicyTile
              label="Check Interval"
              value={
                p.drone_interval_minutes != null
                  ? `${p.drone_interval_minutes} min`
                  : "—"
              }
            />
            <PolicyTile
              label="Next Launch"
              value={
                p.next_launch_time ? formatIstanbulTime(p.next_launch_time) : "—"
              }
            />
            <PolicyTile label="Reason" value={p.reason} wide />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {dronePolicy.error ? "Drone policy unavailable" : "Loading policy..."}
          </p>
        )}
      </div>

      {/* Device discovery strip */}
      <DevicesDetectedStrip />

      {/* Live feeds */}
      <section>
        <div className="flex items-end justify-between mb-3">
          <div>
            <p className="ent-eyebrow">Live Feeds</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1">
              Detection Console
            </h3>
          </div>
          <Badge
            variant="outline"
            className="text-[10px] uppercase tracking-wider"
          >
            Fire detection only — never writes predicted_fwi
          </Badge>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <DroneFeedCard />
          <CameraFeedCard
            camId="webcam"
            title="Webcam Feed"
            deviceLabel="Logitech BRIO 100"
            icon={<Webcam className="h-4 w-4" />}
          />
          <CameraFeedCard
            camId="pc_camera"
            title="PC Camera Feed"
            deviceLabel="Built-in Laptop Camera"
            icon={<Laptop className="h-4 w-4" />}
          />
        </div>
      </section>

      {/* Notifications */}
      <div className="ent-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="ent-eyebrow">Detection Layer</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <ShieldAlert
                className="h-4 w-4"
                style={{ color: "var(--destructive)" }}
              />
              Fire Detection Notifications
            </h3>
          </div>
          <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
            5s refresh
          </Badge>
        </div>
        {notifications.error ? (
          <p className="text-sm text-muted-foreground">
            Notifications unavailable: {notifications.error}
          </p>
        ) : !notifications.data ||
          notifications.data.notifications.length === 0 ? (
          <EmptyNotifications />
        ) : (
          <ul className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {notifications.data.notifications.map((n) => (
              <NotificationRow
                key={n.id}
                notification={n}
                onDelete={() => deleteNotification(n.id)}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ---------- Devices detected strip -----------------------------------------

function DevicesDetectedStrip() {
  const [devices, setDevices] = useState<CameraDevice[]>([]);
  const [runtime, setRuntime] = useState<MonitoringRuntime | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoBusy, setAutoBusy] = useState(false);
  const [autoMsg, setAutoMsg] = useState<string | null>(null);
  const [assignBusy, setAssignBusy] = useState<string | null>(null);

  const probe = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.discoverDevices();
      setDevices(r.devices);
      if (r.runtime) setRuntime(r.runtime);
    } catch {
      // Non-critical — device probe is a helper, not a blocker.
      try {
        setRuntime(await api.getMonitoringRuntime());
      } catch {
        // Runtime copy is advisory only.
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    probe();
  }, [probe]);

  async function runAutoDetect() {
    setAutoBusy(true);
    setAutoMsg(null);
    try {
      const r = await api.autoDetectCameras();
      const wc = r.assignments?.webcam;
      const pc = r.assignments?.pc_camera;
      if (r.reason === "no_devices_opened") {
        setAutoMsg("No cameras opened — connect a device and retry.");
      } else if (r.reason === "single_device_only") {
        setAutoMsg(
          r.brio_detected
            ? `Only one camera connected (appears to be the BRIO → Webcam index ${wc}). Plug in the built-in or second device for full mapping.`
            : `Only one camera connected (built-in → PC Camera index ${pc}). Plug in the Logitech BRIO 100 on another USB port and re-run to assign it to Webcam.`,
        );
      } else if (!r.changed) {
        setAutoMsg("Mapping already optimal — nothing to change.");
      } else {
        setAutoMsg(
          r.brio_detected
            ? `BRIO detected at index ${wc}. Webcam → ${wc}, PC Camera → ${pc}.`
            : `Re-mapped: Webcam → ${wc}, PC Camera → ${pc}.`,
        );
      }
      await probe();
    } catch (e) {
      setAutoMsg((e as Error).message);
    } finally {
      setAutoBusy(false);
    }
  }

  async function assign(camId: string, index: number) {
    setAssignBusy(`${camId}:${index}`);
    setAutoMsg(null);
    try {
      await api.remapCamera(camId, index);
      await probe();
      setAutoMsg(
        `Assigned ${camId === "webcam" ? "Webcam" : "PC Camera"} → index ${index}.`,
      );
    } catch (e) {
      setAutoMsg((e as Error).message);
    } finally {
      setAssignBusy(null);
    }
  }

  return (
    <div className="ent-card p-4">
      <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <HardDrive
            className="h-4 w-4"
            style={{ color: "var(--primary)" }}
          />
          <div>
            <p className="ent-eyebrow">Hardware</p>
            <p className="font-display font-semibold text-sm leading-tight">
              Devices Detected
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-[11px]"
            onClick={runAutoDetect}
            disabled={autoBusy || loading}
            title="Probe every index and assign the highest-resolution camera to Webcam (Logitech BRIO 100)"
          >
            <Wand2
              className={cn("h-3 w-3 mr-1", autoBusy && "animate-pulse")}
            />
            Auto-detect
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-[11px]"
            onClick={probe}
            disabled={loading}
          >
            <RefreshCw
              className={cn("h-3 w-3 mr-1", loading && "animate-spin")}
            />
            Re-probe
          </Button>
        </div>
      </div>
      {autoMsg && (
        <p
          className="text-[11px] mb-2 font-mono-ent"
          style={{ color: "var(--muted-foreground)" }}
        >
          {autoMsg}
        </p>
      )}
      {devices.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">
          {loading
            ? "Probing local camera indices…"
            : cameraUnavailableCopy(runtime)}
        </p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {devices.map((d) => {
            const isBrioClass = d.opened && d.width >= 1920;
            return (
              <div
                key={d.index}
                className="rounded-md border px-3 py-2 flex flex-col gap-1.5"
                style={{
                  borderColor: d.opened ? "var(--primary)" : "var(--border)",
                  background: d.opened
                    ? "color-mix(in srgb, var(--primary) 5%, transparent)"
                    : "var(--muted)",
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono-ent text-xs font-medium">
                    Index {d.index}
                  </span>
                  <span
                    aria-hidden
                    className="ent-status-dot"
                    style={{
                      background: d.opened
                        ? "var(--success)"
                        : "var(--muted-foreground)",
                    }}
                  />
                </div>
                <p className="text-[11px] text-muted-foreground leading-tight">
                  {d.opened
                    ? `${d.width}×${d.height} · ${d.fps} FPS${isBrioClass ? " · likely BRIO" : ""}`
                    : "Not connected"}
                </p>
                {d.assigned_to ? (
                  <Badge
                    variant="outline"
                    className="text-[10px] self-start"
                  >
                    →{" "}
                    {d.assigned_to === "webcam"
                      ? "Webcam (BRIO)"
                      : d.assigned_to === "pc_camera"
                        ? "PC Camera"
                        : d.assigned_to}
                  </Badge>
                ) : (
                  <span className="text-[10px] text-muted-foreground">
                    Unassigned
                  </span>
                )}
                {d.opened && (
                  <div className="flex gap-1 mt-0.5">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 px-1.5 text-[10px] flex-1"
                      onClick={() => assign("webcam", d.index)}
                      disabled={
                        assignBusy !== null || d.assigned_to === "webcam"
                      }
                      title="Assign this device index to the Webcam slot"
                    >
                      <Webcam className="h-2.5 w-2.5 mr-1" />
                      Webcam
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 px-1.5 text-[10px] flex-1"
                      onClick={() => assign("pc_camera", d.index)}
                      disabled={
                        assignBusy !== null || d.assigned_to === "pc_camera"
                      }
                      title="Assign this device index to the PC Camera slot"
                    >
                      <Laptop className="h-2.5 w-2.5 mr-1" />
                      PC Cam
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------- Policy tile -----------------------------------------------------

function PolicyTile({
  label,
  value,
  tone = "neutral",
  wide,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "danger";
  wide?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-md border px-4 py-3",
        wide && "sm:col-span-2 lg:col-span-1",
      )}
      style={{ borderColor: "var(--border)", background: "var(--muted)" }}
    >
      <p className="ent-eyebrow">{label}</p>
      <p
        className="mt-1 text-sm font-medium leading-snug"
        style={{
          color:
            tone === "danger" ? "var(--destructive)" : "var(--foreground)",
        }}
      >
        {value}
      </p>
    </div>
  );
}

// ---------- Feed cards ------------------------------------------------------

function DroneFeedCard() {
  const [status, setStatus] = useState<DroneMonitoringStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Optimistic running state — flipped immediately on click, reconciled on
  // the next status poll. This removes the 5 s "feels dead" gap between
  // pressing Start and seeing the feed image mount.
  const [optimisticRunning, setOptimisticRunning] = useState<boolean | null>(
    null,
  );

  const refresh = useCallback(async () => {
    try {
      const s = await api.getDroneMonitoringStatus();
      setStatus(s);
      // Reconcile optimistic state — the server's truth wins.
      setOptimisticRunning(null);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5_000);
    return () => clearInterval(id);
  }, [refresh]);

  async function toggle() {
    setBusy(true);
    const wasRunning = running;
    setOptimisticRunning(!wasRunning);
    try {
      const s = wasRunning
        ? await api.stopDroneMonitoring()
        : await api.startDroneMonitoring();
      setStatus(s);
      setOptimisticRunning(null);
      setError(null);
    } catch (e) {
      setOptimisticRunning(null);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function emergencyStop() {
    if (!window.confirm("Emergency stop drone?")) return;
    setBusy(true);
    try {
      const s = await api.emergencyStopDrone();
      setStatus(s);
      setOptimisticRunning(null);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const running =
    optimisticRunning !== null ? optimisticRunning : !!status?.running;
  const hwAvailable = status?.hardware_available ?? true;
  const modeLabel = status?.mode
    ? status.mode.charAt(0).toUpperCase() + status.mode.slice(1)
    : "Offline";

  return (
    <FeedCard
      title="Drone Camera"
      subtitle={
        `${modeLabel} mode · ${hwAvailable
          ? status?.battery != null
            ? `Battery ${status.battery}%`
            : "Operator-controlled"
          : "Hardware unavailable"
        }`
      }
      icon={<Plane className="h-4 w-4" />}
      feedPath="/monitoring/drone/feed"
      running={running}
      onToggle={toggle}
      busy={busy}
      disabled={!hwAvailable}
      error={error || status?.last_error || null}
      detectionCount={status?.detection_count ?? 0}
      captureFps={status?.capture_fps}
      inferenceFps={status?.inference_fps}
      extraAction={
        <Button
          size="sm"
          variant="outline"
          onClick={emergencyStop}
          disabled={busy}
          className="w-full"
        >
          Emergency Stop
        </Button>
      }
    />
  );
}

function CameraFeedCard({
  camId,
  title,
  deviceLabel,
  icon,
}: {
  camId: string;
  title: string;
  deviceLabel?: string;
  icon: React.ReactNode;
}) {
  const [status, setStatus] = useState<CameraStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [optimisticRunning, setOptimisticRunning] = useState<boolean | null>(
    null,
  );

  const refresh = useCallback(async () => {
    try {
      const s = await api.getCameraStatus(camId);
      setStatus(s);
      setOptimisticRunning(null);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [camId]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5_000);
    return () => clearInterval(id);
  }, [refresh]);

  async function toggle() {
    setBusy(true);
    const wasRunning = running;
    if (wasRunning) setOptimisticRunning(false);
    try {
      const s = wasRunning
        ? await api.stopCamera(camId)
        : await api.startCamera(camId);
      setStatus(s);
      setOptimisticRunning(null);
      setError(null);
    } catch (e) {
      setOptimisticRunning(null);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const running =
    optimisticRunning !== null ? optimisticRunning : !!status?.running;

  // Build a subtitle that shows the device label (Logitech BRIO / Built-in)
  // alongside the assigned OpenCV index.
  const sub = deviceLabel
    ? `${deviceLabel} · Index ${status?.index ?? "?"}`
    : `OpenCV index ${status?.index ?? "?"}`;

  // Extract a string error from the structured CameraError object.
  const camError = status?.last_error
    ? typeof status.last_error === "object"
      ? status.last_error.code === "device_not_found" ||
        status.last_error.code === "docker_camera_unavailable"
        ? cameraUnavailableCopy()
        : status.last_error.message
      : String(status.last_error)
    : null;

  return (
    <FeedCard
      title={title}
      subtitle={sub}
      icon={icon}
      feedPath={`/monitoring/cameras/${camId}/feed`}
      running={running}
      onToggle={toggle}
      busy={busy}
      error={error || camError}
      detectionCount={status?.detection_count ?? 0}
      captureFps={status?.capture_fps}
      inferenceFps={status?.inference_fps}
    />
  );
}

function cameraUnavailableCopy(runtime?: MonitoringRuntime | null): string {
  if (runtime?.in_docker && !runtime.camera_passthrough_supported) {
    return "Camera is unavailable in Docker. For webcam monitoring, run the backend locally or configure Docker device passthrough.";
  }
  return "Camera is unavailable in this runtime. Check device connection, permissions, or run the backend locally for webcam monitoring.";
}

// ---------- Shared feed card -----------------------------------------------

function FeedCard({
  title,
  subtitle,
  icon,
  feedPath,
  running,
  onToggle,
  busy,
  disabled = false,
  error,
  detectionCount,
  captureFps,
  inferenceFps,
  extraAction,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  feedPath: string;
  running: boolean;
  onToggle: () => void;
  busy: boolean;
  disabled?: boolean;
  error: string | null;
  detectionCount: number;
  captureFps?: number;
  inferenceFps?: number;
  extraAction?: React.ReactNode;
}) {
  // Cache-bust the MJPEG <img> on each start so the browser re-opens the
  // stream instead of reusing a stale connection.
  const [bust, setBust] = useState(0);
  useEffect(() => {
    if (running) setBust(Date.now());
  }, [running]);

  return (
    <div className="ent-card flex flex-col overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-3 border-b"
        style={{ background: "var(--muted)" }}
      >
        <span
          aria-hidden
          className="flex h-8 w-8 items-center justify-center rounded-md"
          style={{
            background: "rgba(7, 44, 44, 0.08)",
            color: "var(--primary)",
          }}
        >
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-display font-semibold text-sm leading-tight truncate">
            {title}
          </p>
          <p className="text-[11px] text-muted-foreground truncate">
            {subtitle}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
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
            {running ? "Live" : "Stopped"}
          </Badge>
          {running && captureFps != null && captureFps > 0 && (
            <span className="text-[10px] font-mono-ent text-muted-foreground">
              {captureFps.toFixed(0)} cap · {(inferenceFps ?? 0).toFixed(0)} inf
            </span>
          )}
        </div>
      </div>

      <div className="p-3">
        <div
          className="relative aspect-video rounded-md overflow-hidden border flex items-center justify-center"
          style={{
            borderColor: "var(--border)",
            background: "#0A1414",
          }}
        >
          {running ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={bust}
              src={`${apiUrl(feedPath)}?t=${bust}`}
              alt={`${title} MJPEG stream`}
              className="w-full h-full object-cover"
              onError={() => setBust((b) => b + 1)}
            />
          ) : (
            <div
              className="flex flex-col items-center gap-2 text-[11px]"
              style={{ color: "#A7B0B0" }}
            >
              <MonitorOff className="h-8 w-8" />
              <span>{disabled ? "Hardware unavailable" : "Feed stopped"}</span>
            </div>
          )}
          {running && detectionCount > 0 && (
            <div className="absolute top-2 right-2">
              <Badge
                variant="destructive"
                className="text-[10px] flex items-center gap-1"
              >
                <AlertTriangle className="h-3 w-3" />
                {detectionCount} fire
              </Badge>
            </div>
          )}
        </div>

        {error && (
          <p
            className="mt-2 text-[11px] leading-snug"
            title={error}
            style={{ color: "var(--destructive)" }}
          >
            {error}
          </p>
        )}
      </div>

      <div className="mt-auto px-3 pb-3 flex gap-2">
        <Button
          size="sm"
          variant={running ? "outline" : "default"}
          onClick={onToggle}
          disabled={busy || disabled}
          className="w-full"
        >
          {running ? (
            <>
              <Square className="h-3 w-3 mr-1" /> Stop feed
            </>
          ) : (
            <>
              <Play className="h-3 w-3 mr-1" /> Start feed
            </>
          )}
        </Button>
        {extraAction}
      </div>
    </div>
  );
}

// ---------- Notifications ---------------------------------------------------

function EmptyNotifications() {
  return (
    <div
      className="rounded-md border border-dashed px-4 py-8 text-center text-sm text-muted-foreground"
      style={{ borderColor: "var(--border)" }}
    >
      No fire detections recorded.
      <p className="text-[11px] mt-1">
        Detections appear here as soon as any live feed&apos;s YOLO detector
        crosses the confidence threshold.
      </p>
    </div>
  );
}

function NotificationRow({
  notification,
  onDelete,
}: {
  notification: MonitoringNotification;
  onDelete: () => void;
}) {
  const n = notification;
  const sourceIcon =
    n.source === "drone" ? (
      <Plane className="h-3 w-3" />
    ) : (
      <Camera className="h-3 w-3" />
    );

  return (
    <li
      className="flex items-center gap-3 rounded-md border px-3 py-2"
      style={{ borderColor: "var(--border)", background: "var(--muted)" }}
    >
      {n.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={apiUrl(n.image)}
          alt={`${n.source} detection at ${n.time_str}`}
          className="h-12 w-16 object-cover rounded border"
          style={{ borderColor: "var(--border)" }}
        />
      ) : (
        <div
          className="h-12 w-16 rounded border flex items-center justify-center"
          style={{ borderColor: "var(--border)", background: "var(--card)" }}
        >
          <Camera
            className="h-4 w-4"
            style={{ color: "var(--muted-foreground)" }}
          />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="text-[10px] flex items-center gap-1"
          >
            {sourceIcon}
            {n.source}
          </Badge>
          <span className="text-[11px] text-muted-foreground font-mono-ent">
            {n.time_str}
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          {n.detection_count} detection{n.detection_count === 1 ? "" : "s"} ·
          max confidence{" "}
          <span className="font-mono-ent text-foreground">
            {(n.max_confidence * 100).toFixed(0)}%
          </span>
        </p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onDelete}
        title="Delete"
        className="h-8 w-8 p-0 shrink-0"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
        <span className="sr-only">Delete</span>
      </Button>
    </li>
  );
}
