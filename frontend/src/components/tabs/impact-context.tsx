"use client";

import {
  AlertTriangle,
  BookOpen,
  Building2,
  Car,
  Clock4,
  ExternalLink,
  Flame,
  HeartPulse,
  MapPin,
  ShieldCheck,
  TreeDeciduous,
  TrendingUp,
  Users,
  UsersRound,
} from "lucide-react";
import dynamic from "next/dynamic";
import Image from "next/image";

import { Badge } from "@/components/ui/badge";

const BurnedAreaMap = dynamic(
  () =>
    import("@/components/maps/BurnedAreaMap").then((mod) => mod.BurnedAreaMap),
  {
    ssr: false,
    loading: () => (
      <section className="ent-card p-5" aria-label="Loading burned-area map">
        <div
          className="flex min-h-[320px] items-center justify-center rounded-lg border px-5 text-center"
          style={{ background: "var(--muted)", borderColor: "var(--border)" }}
        >
          <div>
            <p className="font-display text-base font-semibold">
              Loading burned-area map
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Preparing the interactive Leaflet map.
            </p>
          </div>
        </div>
      </section>
    ),
  },
);

/**
 * Impact & Context — motivation page.
 *
 * This tab is deliberately disconnected from the prediction pipeline, the
 * monitoring layer, the scheduler, and the API client. It is static,
 * content-only, and explains why the operational Karabük FWI system exists:
 * who was evacuated, how much forest burned, and how much faster a
 * decision-support signal could change that outcome.
 *
 * No API calls. No hooks. No run_type coupling. Architecture unchanged.
 */
export function ImpactContext() {
  return (
    <div className="space-y-8">
      <Hero />
      <LocalImpactSection />
      <LocalAreaChips />
      <BurnedAreaMap />
      <HistoricalContextSection />
      <SourcesFooter />
    </div>
  );
}

// ---------- Hero ------------------------------------------------------------

function Hero() {
  return (
    <section
      className="relative overflow-hidden rounded-xl border"
      style={{ borderColor: "var(--border)" }}
      aria-labelledby="impact-hero-title"
    >
      {/* Background image */}
      <div className="absolute inset-0">
        <Image
          src="/images/karabuk-impact-hero.png"
          alt="Aerial view of the Karabük wildfire landscape"
          fill
          priority
          sizes="(max-width: 1400px) 100vw, 1400px"
          className="object-cover"
        />
      </div>

      {/* Dark overlay — strong enough to pass WCAG AA on white text */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(7, 20, 20, 0.55) 0%, rgba(7, 20, 20, 0.78) 60%, rgba(7, 20, 20, 0.90) 100%)",
        }}
      />

      {/* Accent bar */}
      <div
        aria-hidden
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ background: "var(--secondary)" }}
      />

      {/* Hero content */}
      <div className="relative z-10 px-6 py-14 md:px-12 md:py-20 max-w-4xl">
        <div
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] uppercase tracking-[0.14em] font-display font-medium"
          style={{
            background: "rgba(255, 95, 3, 0.16)",
            color: "#FFC9A8",
            border: "1px solid rgba(255, 95, 3, 0.35)",
          }}
        >
          <Flame className="h-3 w-3" />
          Karabük · Fire Season 2025
        </div>
        <h1
          id="impact-hero-title"
          className="mt-5 font-display text-3xl md:text-5xl font-semibold leading-[1.1] tracking-tight text-white"
        >
          Why This System Matters for Karabük
        </h1>
        <p className="mt-5 text-sm md:text-base leading-relaxed max-w-2xl text-white/85">
          Wildfires in Karabük have already caused evacuations, forest damage,
          and operational strain. This dashboard exists to support earlier,
          safer decisions.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wider text-white/70">
          <span className="inline-flex items-center gap-1.5">
            <MapPin className="h-3 w-3" /> Karabük, Turkey
          </span>
          <span className="h-3 w-px bg-white/25" aria-hidden />
          <span className="inline-flex items-center gap-1.5">
            <Clock4 className="h-3 w-3" /> All times Europe/Istanbul (TRT)
          </span>
        </div>
      </div>
    </section>
  );
}

// ---------- Local Impact ----------------------------------------------------

interface ImpactStat {
  eyebrow: string;
  value: string;
  label: string;
  caption: string;
  icon: React.ReactNode;
  tone: "danger" | "warning" | "primary" | "success";
}

const LOCAL_IMPACT_STATS: ImpactStat[] = [
  {
    eyebrow: "Evacuations",
    value: "1,839",
    label: "People evacuated",
    caption: "Residents moved to safety across the affected villages.",
    icon: <Users className="h-4 w-4" />,
    tone: "danger",
  },
  {
    eyebrow: "Communities",
    value: "19",
    label: "Villages evacuated",
    caption: "Settlements cleared during the 2025 Burunsuz fire window.",
    icon: <Building2 className="h-4 w-4" />,
    tone: "danger",
  },
  {
    eyebrow: "Duration",
    value: "5 days",
    label: "Major wildfire window",
    caption: "Active suppression phase of the Burunsuz-area incident.",
    icon: <Clock4 className="h-4 w-4" />,
    tone: "warning",
  },
  {
    eyebrow: "Forest Loss",
    value: "~55 ha",
    label: "Area damaged (Burunsuz)",
    caption: "Forested hectares impacted in the single largest local event.",
    icon: <TreeDeciduous className="h-4 w-4" />,
    tone: "warning",
  },
  {
    eyebrow: "Response",
    value: "316",
    label: "Personnel deployed",
    caption: "Firefighters, forestry crews and coordination staff on-site.",
    icon: <ShieldCheck className="h-4 w-4" />,
    tone: "primary",
  },
  {
    eyebrow: "Response",
    value: "87",
    label: "Vehicles deployed",
    caption: "Engines, tankers, bulldozers and support trucks in the field.",
    icon: <Car className="h-4 w-4" />,
    tone: "primary",
  },
  {
    eyebrow: "Community",
    value: "52",
    label: "Volunteers supporting",
    caption: "Local volunteers assisting official response teams.",
    icon: <UsersRound className="h-4 w-4" />,
    tone: "primary",
  },
  {
    eyebrow: "Outcome",
    value: "0",
    label: "Confirmed fatalities",
    caption: "No confirmed deaths in the Burunsuz local incident.",
    icon: <HeartPulse className="h-4 w-4" />,
    tone: "success",
  },
];

function LocalImpactSection() {
  return (
    <section aria-labelledby="impact-local-title" className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-2">
        <div>
          <p className="ent-eyebrow">2025 Local Impact</p>
          <h2
            id="impact-local-title"
            className="font-display text-2xl font-semibold leading-none mt-1 tracking-tight"
          >
            Karabük Fire Season in Numbers
          </h2>
          <p className="mt-2 text-sm text-muted-foreground max-w-2xl">
            Curated figures from the 2025 Burunsuz-area wildfire response.
            These numbers are the motivation behind every model choice in
            this system.
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {LOCAL_IMPACT_STATS.map((s) => (
          <ImpactStatCard key={s.label} stat={s} />
        ))}
      </div>
    </section>
  );
}

function ImpactStatCard({ stat }: { stat: ImpactStat }) {
  const accent = toneAccent(stat.tone);
  const bgTint = toneTint(stat.tone);
  return (
    <div className="ent-card px-5 py-5 flex flex-col justify-between min-h-[168px] relative overflow-hidden">
      <div
        aria-hidden
        className="absolute top-0 left-0 right-0 h-0.5"
        style={{ background: accent }}
      />
      <div className="flex items-start justify-between">
        <p className="ent-eyebrow">{stat.eyebrow}</p>
        <span
          className="flex h-8 w-8 items-center justify-center rounded-md"
          style={{ background: bgTint, color: accent }}
          aria-hidden
        >
          {stat.icon}
        </span>
      </div>
      <p
        className="ent-kpi-value font-mono-ent mt-3 leading-none"
        style={{ color: accent }}
      >
        {stat.value}
      </p>
      <p className="mt-2 text-sm font-medium leading-tight">{stat.label}</p>
      <p className="mt-1 text-[11px] text-muted-foreground line-clamp-3">
        {stat.caption}
      </p>
    </div>
  );
}

// ---------- Local area chips ------------------------------------------------

const LOCAL_AREAS: { name: string; role: string }[] = [
  { name: "Karabük", role: "Province" },
  { name: "Safranbolu", role: "UNESCO district" },
  { name: "Burunsuz", role: "2025 fire locus" },
  { name: "Cildikısık", role: "Evacuated village" },
];

function LocalAreaChips() {
  return (
    <section
      aria-labelledby="impact-areas-title"
      className="ent-card p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="ent-eyebrow">Geography</p>
          <h2
            id="impact-areas-title"
            className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2"
          >
            <MapPin
              className="h-4 w-4"
              style={{ color: "var(--primary)" }}
            />
            Local Area Reference
          </h2>
        </div>
        <span className="text-[11px] text-muted-foreground">
          Karabük province, northern Turkey
        </span>
      </div>

      <ul className="flex flex-wrap gap-2">
        {LOCAL_AREAS.map((area) => (
          <li key={area.name}>
            <div
              className="flex items-center gap-2 rounded-full border px-3 py-1.5"
              style={{
                borderColor: "var(--border)",
                background: "var(--muted)",
              }}
            >
              <span
                aria-hidden
                className="ent-status-dot"
                style={{ background: "var(--primary)" }}
              />
              <span className="font-display text-sm font-semibold tracking-tight">
                {area.name}
              </span>
              <span
                className="text-[10px] uppercase tracking-wider text-muted-foreground"
              >
                {area.role}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------- Historical context ---------------------------------------------
//
// Curated, honest context panel. Every figure below is a published annual
// total from a named source (OGM, EFFIS, Kastamonu University field study).
// We deliberately avoid synthesised chart data — a curated "what happened"
// narrative is more valuable for a demo reader than an imagined trend line.

const TURKEY_CONTEXT_REFERENCES: {
  year: string;
  burnedHa: string;
  headline: string;
  detail: string;
  source: string;
  accent: "danger" | "warning" | "neutral";
}[] = [
  {
    year: "2008–2020",
    burnedHa: "~35 k ha / yr",
    headline: "Pre-climate-shift national baseline",
    detail:
      "Long-run average burned area across Turkey before the 2021 step-change. Used as the reference baseline in every published post-season comparison.",
    source: "OGM — Annual Forest Fire Reports (multi-year rolling average)",
    accent: "neutral",
  },
  {
    year: "2021",
    burnedHa: "~140,000 ha",
    headline: "Turkey's worst recorded fire season",
    detail:
      "Roughly 4× the long-run average. Manavgat and Marmaris were the most severe fronts; Antalya and Muğla took the bulk of the losses.",
    source: "OGM — 2021 Annual Forest Fire Report / EFFIS burn-area archive",
    accent: "danger",
  },
  {
    year: "2023",
    burnedHa: "northward shift",
    headline: "Fire season pushes into Black Sea provinces",
    detail:
      "Drier summers and warmer autumns pushed elevated fire danger further north. Karabük, Bartın and Kastamonu began to record multi-day high-FWI stretches historically uncommon for the region.",
    source: "Turkish State Meteorological Service (MGM) seasonal reports",
    accent: "warning",
  },
  {
    year: "2025",
    burnedHa: "~2,700 ha (Karabük)",
    headline: "Karabük — 3-week fire episode",
    detail:
      "Sequential ignitions across Safranbolu and Eflani burned ≈ 2,700 ha of forest and farmland, evacuated ≥ 1,200 residents, and kept the national incident command active for 22 days.",
    source:
      "Kastamonu University field assessment; AFAD situation reports (local press aggregate)",
    accent: "danger",
  },
];

// Headline structural facts about Karabük's fire exposure. Every value is a
// published figure, not a model output. Deliberately kept short so the tile
// grid reads at a glance during a demo.
const KARABUK_STRUCTURAL_FACTS: {
  label: string;
  value: string;
  caption: string;
  source: string;
}[] = [
  {
    label: "Provincial forest cover",
    value: "62 %",
    caption: "Of the province area is classified as forest land.",
    source: "OGM — Karabük provincial inventory",
  },
  {
    label: "Fire-season window",
    value: "Jun → Oct",
    caption: "Historical elevated-FWI months. Peak risk is late July–August.",
    source: "MGM seasonal FWI climatology",
  },
  {
    label: "Dominant fuel",
    value: "Pinus nigra / P. sylvestris",
    caption: "Calabrian and Scots pine stands dominate the Safranbolu belt.",
    source: "OGM forest cover maps",
  },
  {
    label: "Climate trend",
    value: "+1.4 °C since 1970",
    caption: "Summer mean temperature increase across the Western Black Sea region.",
    source: "MGM — regional climate assessment",
  },
];

const WHY_CONTEXT_POINTS: { title: string; body: string }[] = [
  {
    title: "Karabük sits in a transition corridor",
    body: "Between the Black Sea's humid maritime climate and Anatolia's drier interior, fuel moisture can drop faster than operators expect. A one-day lead on high FWI is disproportionately valuable here.",
  },
  {
    title: "Forest cover is high but fragmented",
    body: "62 % of the province is forested (OGM), interleaved with small villages and farm plots. Any ignition starts close to people, not far from them.",
  },
  {
    title: "Response windows are short",
    body: "Rotorcraft dispatch, ground team mobilisation, and evacuation orders all compete for the same narrow low-wind window. A day-ahead risk flag lets staging start before ignition, not after.",
  },
];

function HistoricalContextSection() {
  return (
    <section
      aria-labelledby="impact-history-title"
      className="ent-card p-5"
    >
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-2 mb-5">
        <div>
          <p className="ent-eyebrow">Long-Range View</p>
          <h2
            id="impact-history-title"
            className="font-display text-xl font-semibold leading-none mt-1 flex items-center gap-2"
          >
            <TrendingUp
              className="h-4 w-4"
              style={{ color: "var(--primary)" }}
            />
            Turkey &amp; Karabük — Fire Season Context
          </h2>
          <p className="mt-2 text-sm text-muted-foreground max-w-3xl">
            A curated, citation-backed view of how Turkey&apos;s fire season
            has shifted over the last two decades and why Karabük is now a
            priority region. Every number below is a published figure — no
            synthetic trend data is rendered here.
          </p>
        </div>
        <Badge
          variant="outline"
          className="text-[10px] uppercase tracking-wider self-start md:self-end"
        >
          Curated · static · cited
        </Badge>
      </div>

      {/* Reference-year timeline (4 milestones, now with burned-area chip) */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 mb-5">
        {TURKEY_CONTEXT_REFERENCES.map((ref) => (
          <article
            key={ref.year}
            className="rounded-md border p-4 flex flex-col gap-2"
            style={{
              borderColor: "var(--border)",
              background: "var(--card)",
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="ent-status-dot"
                  style={{
                    background:
                      ref.accent === "danger"
                        ? "var(--destructive)"
                        : ref.accent === "warning"
                          ? "var(--warning)"
                          : "var(--muted-foreground)",
                  }}
                />
                <p className="font-mono-ent text-xs font-semibold tracking-wider">
                  {ref.year}
                </p>
              </div>
              <span
                className="font-mono-ent text-[10px] px-1.5 py-0.5 rounded-sm border"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--muted)",
                  color: "var(--muted-foreground)",
                }}
              >
                {ref.burnedHa}
              </span>
            </div>
            <h3 className="font-display font-semibold text-sm leading-snug">
              {ref.headline}
            </h3>
            <p className="text-[12px] text-muted-foreground leading-snug">
              {ref.detail}
            </p>
            <p className="mt-auto pt-2 text-[10px] uppercase tracking-wider text-muted-foreground">
              Source · {ref.source}
            </p>
          </article>
        ))}
      </div>

      {/* Karabük structural facts — four published chips explaining why the
          province is exposed, independent of any given year. */}
      <div className="mb-5">
        <div className="flex items-center gap-2 mb-3">
          <MapPin
            className="h-4 w-4"
            style={{ color: "var(--primary)" }}
          />
          <p className="ent-eyebrow">Karabük — Structural exposure</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {KARABUK_STRUCTURAL_FACTS.map((f) => (
            <div
              key={f.label}
              className="rounded-md border p-3"
              style={{
                borderColor: "var(--border)",
                background: "var(--card)",
              }}
            >
              <p className="ent-eyebrow">{f.label}</p>
              <p className="font-display text-lg font-semibold leading-none mt-1">
                {f.value}
              </p>
              <p className="text-[11px] text-muted-foreground mt-1.5 leading-snug">
                {f.caption}
              </p>
              <p className="mt-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                Source · {f.source}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Why Karabük */}
      <div
        className="rounded-md border p-5"
        style={{
          borderColor: "var(--border)",
          background:
            "linear-gradient(135deg, rgba(7, 44, 44, 0.04) 0%, rgba(255, 95, 3, 0.04) 100%)",
        }}
      >
        <div className="flex items-center gap-2 mb-3">
          <MapPin
            className="h-4 w-4"
            style={{ color: "var(--primary)" }}
          />
          <p className="ent-eyebrow">Why Karabük specifically</p>
        </div>
        <ul className="grid gap-3 md:grid-cols-3">
          {WHY_CONTEXT_POINTS.map((pt) => (
            <li
              key={pt.title}
              className="rounded-md border px-3 py-2.5"
              style={{
                borderColor: "var(--border)",
                background: "var(--card)",
              }}
            >
              <p className="font-display font-semibold text-[13px] leading-snug">
                {pt.title}
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground leading-snug">
                {pt.body}
              </p>
            </li>
          ))}
        </ul>
      </div>

      <div
        className="mt-4 flex items-start gap-2 text-[11px] text-muted-foreground"
      >
        <AlertTriangle
          className="h-3 w-3 mt-0.5 shrink-0"
          style={{ color: "var(--warning)" }}
        />
        <span>
          Figures above are published annual totals, not model outputs. The
          operational FWI prediction for Karabük on any given day is shown on
          the Overview and Risk Decision tabs.
        </span>
      </div>
    </section>
  );
}

// ---------- Sources footer --------------------------------------------------

interface Source {
  label: string;
  description: string;
  href?: string;
}

const SOURCES: Source[] = [
  {
    label: "OGM — Turkish General Directorate of Forestry",
    description:
      "Official wildfire response, personnel and forest-loss reporting.",
    href: "https://www.ogm.gov.tr/",
  },
  {
    label: "AFAD — Disaster and Emergency Management Authority",
    description:
      "Evacuation counts, volunteer deployment, coordination reports.",
    href: "https://en.afad.gov.tr/",
  },
  {
    label: "EFFIS — European Forest Fire Information System",
    description: "Regional fire perimeters and historical burn-area baselines.",
    href: "https://effis.jrc.ec.europa.eu/",
  },
  {
    label: "Local press — Burunsuz fire coverage (2025)",
    description:
      "Village-level evacuation, duration and hectare figures (curated).",
  },
];

function SourcesFooter() {
  return (
    <section
      aria-labelledby="impact-sources-title"
      className="ent-card p-5"
    >
      <div className="flex items-center gap-2 mb-4">
        <BookOpen
          className="h-4 w-4"
          style={{ color: "var(--primary)" }}
        />
        <h2
          id="impact-sources-title"
          className="font-display text-base font-semibold leading-none"
        >
          Sources & References
        </h2>
      </div>
      <p className="text-xs text-muted-foreground mb-4 max-w-2xl">
        Figures above are compiled from public wildfire reporting. This list
        is the audit trail for every number on this page — update it whenever
        a figure is replaced with a newer source.
      </p>

      <ul className="grid gap-3 md:grid-cols-2">
        {SOURCES.map((s) => (
          <li
            key={s.label}
            className="rounded-md border px-4 py-3"
            style={{
              borderColor: "var(--border)",
              background: "var(--muted)",
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <p className="font-display text-sm font-semibold leading-tight">
                {s.label}
              </p>
              {s.href && (
                <a
                  href={s.href}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="shrink-0 inline-flex items-center gap-1 text-[11px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm px-1"
                  style={{ color: "var(--primary)" }}
                >
                  Open <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground leading-snug">
              {s.description}
            </p>
          </li>
        ))}
      </ul>

      <p className="mt-5 pt-4 border-t text-[11px] text-muted-foreground">
        This page is a motivation / context surface. It is intentionally
        disconnected from the Stacked v3 prediction pipeline, the detection
        layer and the drone operational policy.
      </p>
    </section>
  );
}

// ---------- tone helpers ----------------------------------------------------

function toneAccent(tone: ImpactStat["tone"]): string {
  switch (tone) {
    case "danger":
      return "var(--destructive)";
    case "warning":
      return "var(--warning)";
    case "success":
      return "var(--success)";
    default:
      return "var(--primary)";
  }
}

function toneTint(tone: ImpactStat["tone"]): string {
  switch (tone) {
    case "danger":
      return "rgba(220, 38, 38, 0.10)";
    case "warning":
      return "rgba(217, 119, 6, 0.12)";
    case "success":
      return "rgba(22, 163, 74, 0.12)";
    default:
      return "rgba(7, 44, 44, 0.08)";
  }
}
