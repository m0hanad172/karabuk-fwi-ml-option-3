"use client";

import { Flame } from "lucide-react";

import { useT } from "@/lib/i18n-context";
import { cn } from "@/lib/utils";

import {
  NAV_GROUPS,
  NAV_ITEMS,
  type NavGroup,
  type SectionId,
} from "./nav-items";

interface SidebarNavProps {
  activeId: SectionId;
  onSelect: (id: SectionId) => void;
  /** Called when a mobile user taps an item — used to auto-dismiss the drawer. */
  onNavigate?: () => void;
}

/**
 * Left sidebar navigation — brand-forward, grouped, keyboard-accessible.
 *
 * Display strings come from the active language dictionary (see
 * `i18n-context.tsx`). The single source of truth for which items exist
 * is `nav-items.ts`.
 */
export function SidebarNav({ activeId, onSelect, onNavigate }: SidebarNavProps) {
  const t = useT();
  const itemsByGroup = NAV_GROUPS.map((group) => ({
    group,
    items: NAV_ITEMS.filter((i) => i.group === group),
  }));

  return (
    <aside
      className={cn(
        "h-full w-full flex flex-col",
        "bg-sidebar text-sidebar-foreground",
      )}
    >
      {/* Brand block */}
      <div className="px-5 py-4 border-b border-sidebar-border flex items-center gap-3">
        <span
          className="flex h-9 w-9 items-center justify-center rounded-md"
          style={{ background: "rgba(255, 95, 3, 0.14)" }}
          aria-hidden
        >
          <Flame className="h-5 w-5" style={{ color: "#FF5F03" }} />
        </span>
        <div className="min-w-0">
          <p className="font-display text-sm font-semibold tracking-wide uppercase leading-tight">
            {t.brand.name}
          </p>
          <p className="text-[11px] text-sidebar-foreground/60 leading-tight truncate">
            {t.brand.tagline}
          </p>
        </div>
      </div>

      {/* Nav groups */}
      <nav
        aria-label={t.scope.primary}
        className="flex-1 overflow-hidden px-3 py-3 space-y-4"
      >
        {itemsByGroup.map(({ group, items }) => (
          <NavGroupBlock
            key={group}
            group={group}
            items={items}
            activeId={activeId}
            onSelect={(id) => {
              onSelect(id);
              onNavigate?.();
            }}
          />
        ))}
      </nav>

      {/* Scope footer */}
      <div className="px-5 py-3 border-t border-sidebar-border text-[10px] leading-snug text-sidebar-foreground/60">
        <p className="font-display uppercase tracking-widest text-[10px] text-sidebar-foreground/50">
          {t.sidebar.scopeLabel}
        </p>
        <p className="mt-1">{t.sidebar.scopeLocation}</p>
        <p>{t.sidebar.scopeTimezone}</p>
      </div>
    </aside>
  );
}

function NavGroupBlock({
  group,
  items,
  activeId,
  onSelect,
}: {
  group: NavGroup;
  items: typeof NAV_ITEMS;
  activeId: SectionId;
  onSelect: (id: SectionId) => void;
}) {
  const t = useT();
  return (
    <div>
      <p className="px-2 ent-eyebrow mb-2 text-sidebar-foreground/50">
        {t.groups[group]}
      </p>
      <ul role="list" className="space-y-0.5">
        {items.map((item) => {
          const Icon = item.icon;
          const active = item.id === activeId;
          const label = t.nav[item.id].label;
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onSelect(item.id)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group w-full flex items-center gap-3 rounded-md px-3 py-1.5",
                  "text-sm font-medium transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2",
                  "focus-visible:ring-sidebar-ring focus-visible:ring-offset-2",
                  "focus-visible:ring-offset-sidebar",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "h-1.5 w-1.5 rounded-full transition-colors",
                    active ? "bg-sidebar-primary" : "bg-transparent",
                  )}
                />
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    active
                      ? "text-sidebar-primary"
                      : "text-sidebar-foreground/70 group-hover:text-sidebar-foreground",
                  )}
                />
                <span className="truncate">{label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
