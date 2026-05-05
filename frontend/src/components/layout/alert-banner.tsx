"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { StatusToast } from "@/components/ui/status-toast";
import { api, snapshotUrl, type DetectionAlert } from "@/lib/api";

const POLL_MS = 5_000;
const AUTO_DISMISS_MS = 12_000;

export function AlertBanner() {
  const [active, setActive] = useState<DetectionAlert | null>(null);
  const [snapshotFailed, setSnapshotFailed] = useState(false);
  const seenIdRef = useRef<string | null>(null);
  const initialisedRef = useRef(false);
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
    setActive(null);
  }, []);

  useEffect(() => {
    setSnapshotFailed(false);
  }, [active?.id]);

  useEffect(() => {
    let cancelled = false;
    let lastInflight = false;

    const poll = async () => {
      if (lastInflight) return;
      lastInflight = true;
      try {
        const { alert } = await api.getLatestDetectionAlert();
        if (cancelled) return;

        if (!alert) {
          initialisedRef.current = true;
          return;
        }

        if (!initialisedRef.current) {
          seenIdRef.current = alert.id;
          initialisedRef.current = true;
          return;
        }

        if (alert.id !== seenIdRef.current) {
          seenIdRef.current = alert.id;
          setSnapshotFailed(false);
          setActive(alert);
          if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
          dismissTimerRef.current = setTimeout(() => {
            setActive(null);
            dismissTimerRef.current = null;
          }, AUTO_DISMISS_MS);
        }
      } catch {
        // Detection Alerts surfaces backend fetch errors; the global toast
        // should stay quiet when the backend is temporarily unreachable.
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
  const snapshot =
    active.image && !snapshotFailed
      ? snapshotUrl(active.image, active.snapshot_version)
      : undefined;

  return (
    <StatusToast
      toast={{
        role: "alert",
        title: isFire ? "Fire detected" : "Smoke detected",
        message: [
          sourceLabel(active.source),
          confPct ? `${confPct} confidence` : null,
          active.time_str,
        ]
          .filter(Boolean)
          .join(" · "),
        tone: isFire ? "danger" : "warning",
        imageUrl: snapshot,
        imageAlt: `${label} detection snapshot`,
      }}
      onClose={dismiss}
      onImageError={() => setSnapshotFailed(true)}
    />
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
      return "Demo";
    case "manual":
      return "Manual";
    default:
      return source ?? "Unknown source";
  }
}
