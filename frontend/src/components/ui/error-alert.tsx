"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";

/**
 * Standardised error surface for API / data failures.
 *
 * Every tab in the dashboard funnels API errors through `useApi`, which
 * returns a plain `error: string | null`. Before this component each tab
 * rendered that string differently — muted paragraphs, inline red text,
 * destructive badges — which made the dashboard look inconsistent and
 * let real problems hide in low-contrast corners during a demo.
 *
 * Usage:
 *
 *     {foo.error && (
 *       <ErrorAlert
 *         title="Could not load model metadata"
 *         message={foo.error}
 *         onRetry={foo.refetch}
 *       />
 *     )}
 *
 * The component is intentionally passive — it does NOT swallow loading
 * state. Callers decide whether to render the alert alongside a skeleton,
 * instead of a skeleton, or after the skeleton. Passing `compact` trims
 * the vertical padding for inline use inside existing cards.
 */
export function ErrorAlert({
  title,
  message,
  onRetry,
  compact = false,
}: {
  title: string;
  message?: string | null;
  onRetry?: () => void;
  compact?: boolean;
}) {
  return (
    <div
      role="alert"
      className={`rounded-md border flex items-start gap-3 ${
        compact ? "px-3 py-2" : "px-4 py-3"
      }`}
      style={{
        borderColor: "var(--destructive)",
        background: "color-mix(in oklab, var(--destructive) 8%, transparent)",
      }}
    >
      <AlertTriangle
        className="h-4 w-4 flex-shrink-0 mt-0.5"
        style={{ color: "var(--destructive)" }}
        aria-hidden
      />
      <div className="flex-1 min-w-0">
        <p
          className="text-sm font-medium leading-tight"
          style={{ color: "var(--destructive)" }}
        >
          {title}
        </p>
        {message && (
          <p
            className="text-xs mt-1 break-words font-mono-ent"
            style={{ color: "var(--destructive)" }}
          >
            {message}
          </p>
        )}
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="text-[11px] uppercase tracking-wider font-medium flex items-center gap-1 rounded px-2 py-1 border transition-colors hover:bg-[var(--destructive)] hover:text-white"
          style={{
            borderColor: "var(--destructive)",
            color: "var(--destructive)",
          }}
        >
          <RefreshCw className="h-3 w-3" aria-hidden />
          Retry
        </button>
      )}
    </div>
  );
}
