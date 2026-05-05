"use client";

import { Button } from "@/components/ui/button";

export type StatusToastTone = "success" | "warning" | "danger" | "neutral";

export interface StatusToastState {
  title: string;
  message: string;
  tone?: StatusToastTone;
  role?: "status" | "alert";
  imageUrl?: string;
  imageAlt?: string;
}

export function StatusToast({
  toast,
  onClose,
  onImageError,
}: {
  toast: StatusToastState | null;
  onClose: () => void;
  onImageError?: () => void;
}) {
  if (!toast) return null;

  const border =
    toast.tone === "danger"
      ? "var(--destructive)"
      : toast.tone === "warning"
        ? "var(--warning)"
        : toast.tone === "success"
          ? "var(--success)"
          : "var(--border)";

  return (
    <div
      role={toast.role ?? "status"}
      aria-live={toast.role === "alert" ? "assertive" : "polite"}
      className="fixed right-4 top-20 z-[9999] w-[calc(100vw-2rem)] max-w-sm rounded-md border px-4 py-3 text-sm shadow-xl"
      style={{
        background: "var(--card)",
        borderColor: border,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium leading-tight">{toast.title}</p>
          <p className="mt-1 text-xs text-muted-foreground leading-snug">
            {toast.message}
          </p>
          {toast.imageUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={toast.imageUrl}
              alt={toast.imageAlt ?? ""}
              onError={onImageError}
              className="mt-2 max-h-24 w-full rounded-sm border object-cover"
              style={{ borderColor: "var(--border)" }}
            />
          )}
        </div>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-6 shrink-0 px-2 text-[11px]"
          onClick={onClose}
        >
          Close
        </Button>
      </div>
    </div>
  );
}
