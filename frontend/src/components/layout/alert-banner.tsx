"use client";

import { AlertTriangle, Bell, Flame, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, apiUrl, type DetectionAlert } from "@/lib/api";

/**
 * Visible in-app banner that fires when a new fire/smoke detection
 * lands in the JSONL evidence log.
 *
 * Why this lives in the app shell, not the Detection Alerts tab:
 *  - It must be visible across every tab — the supervisor should see
 *    a fresh detection regardless of where they happened to be on the
 *    dashboard.
 *  - The Detection Alerts tab is the *audit* surface; the banner is
 *    the *attention* surface. Keeping them separate matches the
 *    architectural rule that detection is a strictly read-only
 *    observation channel and never gets entangled with the prediction
 *    pipeline.
 *
 * How it stays cheap:
 *  - Polls only `GET /monitoring/alerts/latest` (returns one alert or
 *    null, ~200 bytes) every {@link POLL_MS}.
 *  - Diffs by alert id against the previously-seen id stored in a ref,
 *    so re-renders never re-fire the banner.
 *  - The very first poll after page load primes the ref but does NOT
 *    trigger the banner — otherwise every reload would feel like a new
 *    detection.
 */
const POLL_MS = 5_000;
const AUTO_DISMISS_MS = 12_000;

export function AlertBanner() {
  const [active, setActive] = useState<DetectionAlert | null>(null);
  // Tracks the id of the most recently observed alert across polls.
  // Initialised on the first successful response — without this guard
  // the banner would fire on every fresh page load for the existing
  // last alert in the log.
  const seenIdRef = useRef<string | null>(null);
  const initialisedRef = useRef(false);

  // Auto-dismiss timer — cleared if the user dismisses manually or a
  // newer alert arrives.
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
    setActive(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let lastInflight = false;

    const poll = async () => {
      // Skip if a previous fetch is still pending — prevents pile-up
      // if the backend stalls for a few seconds.
      if (lastInflight) return;
      lastInflight = true;
      try {
        const { alert } = await api.getLatestDetectionAlert();
        if (cancelled) return;
        if (!alert) {
          // Nothing yet — prime the "initialised" flag so a future
          // first-ever alert is treated as new and surfaces.
          initialisedRef.current = true;
          return;
        }

        if (!initialisedRef.current) {
          // First poll after mount: remember the latest id but DO NOT
          // raise a banner. The user came here to view the dashboard,
          // not to be told about a stale alert.
          seenIdRef.current = alert.id;
          initialisedRef.current = true;
          return;
        }

        if (alert.id !== seenIdRef.current) {
          seenIdRef.current = alert.id;
          setActive(alert);
          if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
          dismissTimerRef.current = setTimeout(() => {
            setActive(null);
            dismissTimerRef.current = null;
          }, AUTO_DISMISS_MS);
        }
      } catch {
        // Backend is unreachable / the smoke-test client is down.
        // Silently swallow — we'll try again next tick. The Detection
        // Alerts tab itself surfaces the underlying error.
      } finally {
        lastInflight = false;
      }
    };

    poll();
    const interval = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    };
  }, []);

  if (!active) return null;

  const label = active.detections?.[0]?.label ?? "fire";
  const isFire = label.toLowerCase() === "fire";
  const confPct =
    active.max_confidence != null
      ? `${(active.max_confidence * 100).toFixed(1)}%`
      : null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed top-4 right-4 z-50 max-w-sm shadow-lg rounded-md border bg-background"
      style={{
        // Fire = red destructive accent; smoke = warning amber.
        borderColor: isFire
          ? "var(--destructive, #b91c1c)"
          : "rgba(180, 120, 30, 0.55)",
      }}
    >
      <div className="flex gap-3 p-4">
        <div
          aria-hidden
          className="mt-0.5 shrink-0"
          style={{
            color: isFire
              ? "var(--destructive, #b91c1c)"
              : "rgb(180, 120, 30)",
          }}
        >
          {isFire ? (
            <Flame className="h-5 w-5" />
          ) : (
            <AlertTriangle className="h-5 w-5" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm flex items-center gap-1.5">
            <Bell className="h-3.5 w-3.5" aria-hidden />
            {isFire ? "Fire detected" : "Smoke detected"}
          </p>
          <p className="text-xs text-muted-foreground mt-1 truncate">
            {sourceLabel(active.source)}
            {confPct ? ` · ${confPct} confidence` : ""}
            {active.time_str ? ` · ${active.time_str}` : ""}
          </p>
          {active.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={apiUrl(active.image)}
              alt={`${label} detection snapshot`}
              className="mt-2 rounded-sm border"
              style={{
                maxWidth: "100%",
                maxHeight: 96,
                objectFit: "cover",
                borderColor: "var(--border)",
              }}
            />
          )}
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss alert"
          className="shrink-0 rounded p-1 hover:bg-muted text-muted-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function sourceLabel(source: string | null | undefined): string {
  switch (source) {
    case "drone":
      return "Drone";
    case "webcam":
      return "Webcam";
    case "pc_camera":
      return "PC Camera";
    case "demo":
      return "Demo (synthetic)";
    case "manual":
      return "Manual";
    default:
      return source ?? "Unknown source";
  }
}
