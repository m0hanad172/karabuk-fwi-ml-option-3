"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorBoundary } from "@/components/error-boundary";
import { DetectionAlerts } from "@/components/tabs/detection-alerts";
import { FeaturesInputs } from "@/components/tabs/features-inputs";
import { HistoricalAnalytics } from "@/components/tabs/historical-analytics";
import { ImpactContext } from "@/components/tabs/impact-context";
import { LiveOverview } from "@/components/tabs/live-overview";
import { MonitoringDrone } from "@/components/tabs/monitoring-drone";
import { RiskDecision } from "@/components/tabs/risk-decision";
import { RunHistory } from "@/components/tabs/run-history";
import { SystemFlow } from "@/components/tabs/system-flow";
import { SystemModel } from "@/components/tabs/system-model";
import { useT } from "@/lib/i18n-context";
import { cn } from "@/lib/utils";

import { DEFAULT_SECTION, findNavItem, type SectionId } from "./nav-items";
import { PageHeader } from "./page-header";
import { SidebarNav } from "./sidebar-nav";
import { TopBar } from "./top-bar";

/**
 * Top-level application shell: left sidebar + sticky top bar + content.
 *
 * - Overview is the default landing section.
 * - Each section mounts exactly one of the existing tab components
 *   inside an ErrorBoundary so one failing page cannot take the app down.
 * - Mobile: the sidebar collapses into a slide-over sheet; desktop: it
 *   is a permanent 260px column.
 *
 * NOTE: This file is the ONLY place that knows which component maps to
 * which SectionId. Adding a new section means: add to nav-items.ts, then
 * add one branch here.
 */
export function AppShell() {
  const [active, setActive] = useState<SectionId>(DEFAULT_SECTION);
  const [mobileOpen, setMobileOpen] = useState(false);
  const t = useT();

  // Close mobile drawer whenever a nav item is selected or the viewport
  // grows past the breakpoint.
  useEffect(() => {
    if (!mobileOpen) return;
    const onResize = () => {
      if (window.innerWidth >= 1024) setMobileOpen(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [mobileOpen]);

  const activeItem = findNavItem(active);
  const activeNav = t.nav[active];
  const activeGroupLabel = t.groups[activeItem.group];

  const select = useCallback((id: SectionId) => {
    setActive(id);
  }, []);

  return (
    <div className="flex min-h-screen w-full">
      {/* Desktop sidebar — permanent column */}
      <div className="hidden lg:flex lg:w-[260px] lg:flex-shrink-0">
        <SidebarNav activeId={active} onSelect={select} />
      </div>

      {/* Mobile sidebar — slide-over sheet */}
      <MobileSidebar
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        activeId={active}
        onSelect={select}
      />

      <div className="flex flex-col flex-1 min-w-0">
        <TopBar active={activeItem} onMenu={() => setMobileOpen(true)} />

        <main className="flex-1 px-4 md:px-8 py-6 md:py-8">
          <div className="max-w-[1400px] mx-auto">
            <PageHeader
              eyebrow={activeGroupLabel}
              title={activeNav.label}
              description={activeNav.sub}
            />

            <SectionRenderer id={active} />
          </div>
        </main>

        <footer className="border-t px-4 md:px-8 py-3 text-[11px] text-muted-foreground">
          <div className="max-w-[1400px] mx-auto flex flex-wrap items-center justify-between gap-2">
            <span>{t.footer.productLine}</span>
            <span>{t.footer.scope}</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

function SectionRenderer({ id }: { id: SectionId }) {
  switch (id) {
    case "overview":
      return (
        <ErrorBoundary fallbackTitle="Overview failed to load">
          <LiveOverview />
        </ErrorBoundary>
      );
    case "impact":
      return (
        <ErrorBoundary fallbackTitle="Impact & Context failed to load">
          <ImpactContext />
        </ErrorBoundary>
      );
    case "risk":
      return (
        <ErrorBoundary fallbackTitle="Risk Decision failed to load">
          <RiskDecision />
        </ErrorBoundary>
      );
    case "features":
      return (
        <ErrorBoundary fallbackTitle="Features failed to load">
          <FeaturesInputs />
        </ErrorBoundary>
      );
    case "analytics":
      return (
        <ErrorBoundary fallbackTitle="Historical Analytics failed to load">
          <HistoricalAnalytics />
        </ErrorBoundary>
      );
    case "history":
      return (
        <ErrorBoundary fallbackTitle="Run History failed to load">
          <RunHistory />
        </ErrorBoundary>
      );
    case "monitoring":
      return (
        <ErrorBoundary fallbackTitle="Monitoring failed to load">
          <MonitoringDrone />
        </ErrorBoundary>
      );
    case "alerts":
      return (
        <ErrorBoundary fallbackTitle="Detection Alerts failed to load">
          <DetectionAlerts />
        </ErrorBoundary>
      );
    case "system":
      return (
        <ErrorBoundary fallbackTitle="System Info failed to load">
          <SystemModel />
        </ErrorBoundary>
      );
    case "flow":
      return (
        <ErrorBoundary fallbackTitle="System Flow failed to load">
          <SystemFlow />
        </ErrorBoundary>
      );
  }
}

function MobileSidebar({
  open,
  onClose,
  activeId,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  activeId: SectionId;
  onSelect: (id: SectionId) => void;
}) {
  return (
    <div
      className={cn(
        "lg:hidden fixed inset-0 z-40 transition",
        open ? "pointer-events-auto" : "pointer-events-none",
      )}
      aria-hidden={!open}
    >
      <div
        className={cn(
          "absolute inset-0 bg-black/40 transition-opacity",
          open ? "opacity-100" : "opacity-0",
        )}
        onClick={onClose}
      />
      <div
        className={cn(
          "absolute inset-y-0 left-0 w-[280px] shadow-xl transition-transform",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        role="dialog"
        aria-modal="true"
        aria-label="Primary navigation"
      >
        <SidebarNav
          activeId={activeId}
          onSelect={onSelect}
          onNavigate={onClose}
        />
      </div>
    </div>
  );
}
