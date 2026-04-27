"use client";

import { Languages } from "lucide-react";

import { useLang, useSetLang, useT } from "@/lib/i18n-context";
import { LANGS, type Lang } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * Segmented EN / TR toggle rendered in the top bar.
 *
 * A segmented control (not a dropdown) because there are only two
 * options — tapping is one click instead of two, and both choices stay
 * visible so the user always knows the toggle exists. Matches the
 * enterprise UI's preference for explicit, low-chrome controls.
 */
export function LanguageSwitcher({ className }: { className?: string }) {
  const lang = useLang();
  const setLang = useSetLang();
  const t = useT();

  return (
    <div
      role="group"
      aria-label={t.switcher.ariaLabel}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-1 py-1 text-[11px] font-medium",
        className,
      )}
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <Languages
        className="h-3.5 w-3.5 ml-1 mr-0.5"
        style={{ color: "var(--primary)" }}
        aria-hidden
      />
      {LANGS.map((code) => {
        const active = code === lang;
        const label = code === "en" ? t.switcher.en : t.switcher.tr;
        const full = code === "en" ? t.switcher.enFull : t.switcher.trFull;
        return (
          <button
            key={code}
            type="button"
            onClick={() => setLang(code as Lang)}
            aria-pressed={active}
            title={full}
            className={cn(
              "rounded-full px-2 py-0.5 transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
