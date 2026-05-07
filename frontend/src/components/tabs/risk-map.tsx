"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

// The Leaflet-backed map renders only on the client; SSR-disabled so
// the static export never crashes when navigating to this tab.
const BurnedAreaMap = dynamic(
  () =>
    import("@/components/maps/BurnedAreaMap").then((mod) => mod.BurnedAreaMap),
  {
    ssr: false,
    loading: () => (
      <section
        className="ent-card p-5"
        aria-label="Loading burned-area map"
      >
        <Skeleton className="h-[420px] w-full" />
      </section>
    ),
  },
);

/**
 * Risk Map — historical fire context.
 *
 * Standalone tab dedicated to the 2025 Karabük burned-area map. The map
 * itself is the same `BurnedAreaMap` component the Impact tab used to
 * render; everything else on this page is short, professional context
 * that supports drone station and patrol planning.
 *
 * No API calls, no scheduler coupling, no dashboard polling. Static
 * GeoJSON consumed at module load.
 */
export function RiskMap() {
  return (
    <div className="space-y-4">
      <BurnedAreaMap />

      <section
        className="ent-card p-4 text-sm leading-relaxed text-muted-foreground"
        aria-label="Planning note"
      >
        <p>
          This map supports historical fire context and helps identify
          sensitive areas for future drone station and patrol planning.
        </p>
      </section>
    </div>
  );
}
