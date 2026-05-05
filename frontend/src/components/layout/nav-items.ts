/**
 * Sidebar navigation registry.
 *
 * Single source of truth for what sections exist in the app. Adding or
 * removing a page happens here — the AppShell renderer and the sidebar
 * UI both read from this list. Order matters: the first "main" item
 * (Overview) is the default landing page.
 *
 * Display labels/subtitles are NOT stored here — they are resolved at
 * render time from the i18n dictionary (`t.nav[id].label` /
 * `t.nav[id].sub`) so swapping languages re-labels everything without
 * touching this registry.
 */
import {
  Activity,
  BarChart3,
  Bell,
  Gauge,
  Globe2,
  History,
  LayoutDashboard,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export type SectionId =
  | "overview"
  | "impact"
  | "risk"
  | "features"
  | "analytics"
  | "history"
  | "monitoring"
  | "alerts"
  | "system"
  | "flow";

export type NavGroup = "Main" | "Operations" | "System";

export interface NavItem {
  id: SectionId;
  group: NavGroup;
  icon: LucideIcon;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { id: "overview", group: "Main", icon: LayoutDashboard },
  { id: "impact", group: "Main", icon: Globe2 },
  { id: "risk", group: "Main", icon: Gauge },
  { id: "analytics", group: "Main", icon: BarChart3 },
  { id: "history", group: "Operations", icon: History },
  { id: "alerts", group: "Operations", icon: Bell },
  { id: "system", group: "System", icon: Activity },
  { id: "flow", group: "System", icon: Workflow },
] as const;

export const DEFAULT_SECTION: SectionId = "overview";

export const NAV_GROUPS: readonly NavGroup[] = ["Main", "Operations", "System"];

export function findNavItem(id: SectionId): NavItem {
  const found = NAV_ITEMS.find((n) => n.id === id);
  if (!found) throw new Error(`Unknown section ${id}`);
  return found;
}
