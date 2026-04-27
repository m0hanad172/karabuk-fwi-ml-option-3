"use client";

import { Clock, MapPin, Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n-context";

import { LanguageSwitcher } from "./language-switcher";
import type { NavItem } from "./nav-items";

interface TopBarProps {
  active: NavItem;
  onMenu: () => void;
}

/**
 * Sticky top bar — active section title, always-visible Karabük /
 * Istanbul scope chips, and the language switcher. The mobile hamburger
 * is rendered here so the sidebar can slide in from the side on small
 * screens.
 */
export function TopBar({ active, onMenu }: TopBarProps) {
  const Icon = active.icon;
  const t = useT();
  const label = t.nav[active.id].label;
  return (
    <header
      className="sticky top-0 z-20 flex items-center gap-4 border-b bg-background/95 backdrop-blur px-4 md:px-8 py-3 md:py-4"
      style={{ borderColor: "var(--border)" }}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={onMenu}
        aria-label={t.topbar.openMenu}
      >
        <Menu className="h-5 w-5" />
      </Button>

      <div className="flex items-center gap-3 min-w-0">
        <span
          aria-hidden
          className="hidden sm:flex h-9 w-9 items-center justify-center rounded-md"
          style={{
            background: "rgba(7, 44, 44, 0.08)",
            color: "var(--primary)",
          }}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="ent-eyebrow">{t.topbar.consoleEyebrow}</p>
          <h1 className="font-display text-lg md:text-xl font-semibold leading-tight truncate">
            {label}
          </h1>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2 md:gap-3">
        <ScopeChip
          icon={<MapPin className="h-3.5 w-3.5" />}
          label={t.topbar.karabukChip}
        />
        <ScopeChip
          icon={<Clock className="h-3.5 w-3.5" />}
          label={t.topbar.istanbulChip}
        />
        <LanguageSwitcher />
      </div>
    </header>
  );
}

function ScopeChip({
  icon,
  label,
}: {
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <span
      className="hidden md:inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
        color: "var(--foreground)",
      }}
    >
      <span aria-hidden style={{ color: "var(--primary)" }}>
        {icon}
      </span>
      {label}
    </span>
  );
}
