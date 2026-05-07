"use client";

import {
  Activity,
  ArrowRight,
  Bell,
  Camera,
  CloudSun,
  Database,
  Gauge,
  Layers,
  LayoutDashboard,
  Monitor,
  ShieldCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react";

type FlowStep = {
  title: string;
  caption: string;
  icon: LucideIcon;
};

const MAIN_FLOW: FlowStep[] = [
  {
    title: "Daily Weather Data",
    caption: "daily aggregates",
    icon: CloudSun,
  },
  {
    title: "34 Features",
    caption: "34 model features",
    icon: Layers,
  },
  {
    title: "Stage 1 Regression",
    caption: "predicts FWI",
    icon: Activity,
  },
  {
    title: "predicted_fwi",
    caption: "daily FWI",
    icon: Gauge,
  },
  {
    title: "Stage 2 Classifier",
    caption: "safety layer",
    icon: ShieldCheck,
  },
  {
    title: "Risk Probability",
    caption: "high-risk score",
    icon: Gauge,
  },
  {
    title: "Risk Decision",
    caption: "risk class",
    icon: Workflow,
  },
];

const NORMAL_BRANCH: FlowStep[] = [
  {
    title: "Fixed Monitoring",
    caption: "CCTV active",
    icon: Monitor,
  },
  {
    title: "Dashboard Update",
    caption: "status refreshed",
    icon: LayoutDashboard,
  },
];

const HIGH_RISK_BRANCH: FlowStep[] = [
  {
    title: "Patrol Ready",
    caption: "patrol recommended",
    icon: ShieldCheck,
  },
  {
    title: "Live Sources",
    caption: "camera feeds",
    icon: Camera,
  },
  {
    title: "Fire/Smoke Detection",
    caption: "vision monitoring",
    icon: Activity,
  },
  {
    title: "Alerts + SQLite",
    caption: "saved alerts",
    icon: Database,
  },
  {
    title: "Dashboard Action",
    caption: "operator response",
    icon: Bell,
  },
];

const SUPPORT_CARDS = [
  {
    title: "Scheduled Checks",
    caption: "Europe/Istanbul",
    chips: ["09:00", "11:00", "15:00"],
  },
  {
    title: "Risk Classes",
    caption: "dashboard status",
    chips: ["Low", "Moderate", "High"],
  },
  {
    title: "Monitoring Sources",
    caption: "detection inputs",
    chips: ["Drone", "Webcam", "PC Camera"],
  },
  {
    title: "Storage",
    caption: "SQLite tables",
    chips: ["run_history", "system_state", "detection_alerts"],
  },
];

export function SystemFlow() {
  return (
    <div className="space-y-5">
      <section className="ent-card p-5">
        <p className="ent-eyebrow">System Flow</p>
        <div className="mt-1 flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-display text-2xl font-semibold leading-tight">
              System Flow
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              From daily weather input to operational monitoring and alerts.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            <Badge>daily aggregates</Badge>
            <Badge>two-stage model</Badge>
            <Badge>operator action</Badge>
          </div>
        </div>
      </section>

      <section className="ent-card p-4" aria-labelledby="main-flow-title">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="ent-eyebrow">Prediction path</p>
            <h3
              id="main-flow-title"
              className="font-display text-lg font-semibold leading-tight"
            >
              Weather to risk decision
            </h3>
          </div>
        </div>
        <FlowLine steps={MAIN_FLOW} />
      </section>

      <section aria-label="Risk decision branches" className="grid gap-4">
        <BranchCard
          label="If Normal / Moderate"
          title="Fixed monitoring continues"
          tone="primary"
          steps={NORMAL_BRANCH}
        />
        <BranchCard
          label="If High Risk"
          title="Patrol-ready monitoring"
          tone="secondary"
          steps={HIGH_RISK_BRANCH}
        />
      </section>

      <section
        aria-label="System flow supporting facts"
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
      >
        {SUPPORT_CARDS.map((card) => (
          <SupportCard key={card.title} {...card} />
        ))}
      </section>
    </div>
  );
}

function FlowLine({ steps }: { steps: FlowStep[] }) {
  return (
    <ol className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-7">
      {steps.map((step, index) => (
        <li key={step.title} className="min-w-0">
          <FlowBox
            step={step}
            stepNumber={index + 1}
            showArrow={index < steps.length - 1}
          />
        </li>
      ))}
    </ol>
  );
}

function BranchCard({
  label,
  title,
  tone,
  steps,
}: {
  label: string;
  title: string;
  tone: "primary" | "secondary";
  steps: FlowStep[];
}) {
  const accent = tone === "secondary" ? "var(--secondary)" : "var(--primary)";

  return (
    <article className="ent-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="ent-eyebrow" style={{ color: accent }}>
            {label}
          </p>
          <h3 className="font-display text-lg font-semibold leading-tight">
            {title}
          </h3>
        </div>
      </div>
      <ol
        className={`grid min-w-0 gap-3 ${
          steps.length > 2
            ? "sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5"
            : "sm:grid-cols-2"
        }`}
      >
        {steps.map((step, index) => (
          <li key={step.title} className="min-w-0">
            <FlowBox
              step={step}
              accent={accent}
              stepNumber={index + 1}
              showArrow={index < steps.length - 1}
            />
          </li>
        ))}
      </ol>
    </article>
  );
}

function FlowBox({
  step,
  accent = "var(--primary)",
  stepNumber,
  showArrow = false,
}: {
  step: FlowStep;
  accent?: string;
  stepNumber?: number;
  showArrow?: boolean;
}) {
  const Icon = step.icon;

  return (
    <div
      className="relative flex h-full min-h-[112px] min-w-0 flex-col overflow-hidden rounded-md border p-3"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <div className="mb-2 flex min-w-0 items-center justify-between gap-2">
        {stepNumber ? (
          <span
            className="flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full border px-1 font-mono-ent text-[10px] font-semibold leading-none"
            style={{
              borderColor: "var(--border)",
              background: "var(--background)",
              color: accent,
            }}
          >
            {stepNumber}
          </span>
        ) : null}
        {showArrow ? (
          <ArrowRight
            className="hidden h-4 w-4 shrink-0 text-muted-foreground 2xl:block"
            aria-hidden
          />
        ) : null}
      </div>
      <div className="flex items-start gap-2">
        <span
          className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border"
          style={{
            borderColor: "var(--border)",
            background: "var(--background)",
            color: accent,
          }}
          aria-hidden
        >
          <Icon className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="whitespace-normal break-words font-display text-[13px] font-semibold leading-snug">
            {step.title}
          </p>
          <p className="mt-1 whitespace-normal break-words text-[11px] leading-snug text-muted-foreground">
            {step.caption}
          </p>
        </div>
      </div>
    </div>
  );
}

function SupportCard({
  title,
  caption,
  chips,
}: {
  title: string;
  caption: string;
  chips: string[];
}) {
  return (
    <article
      className="rounded-md border p-3"
      style={{ borderColor: "var(--border)", background: "var(--muted)" }}
    >
      <p className="font-display text-sm font-semibold leading-tight">
        {title}
      </p>
      <p className="mt-0.5 text-[11px] text-muted-foreground">{caption}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {chips.map((chip) => (
          <Badge key={chip}>{chip}</Badge>
        ))}
      </div>
    </article>
  );
}

function Badge({ children }: { children: string }) {
  return (
    <span
      className="inline-flex max-w-full items-center rounded-sm border px-2 py-1 text-[11px] font-medium leading-tight break-words"
      style={{ borderColor: "var(--border)", background: "var(--background)" }}
    >
      {children}
    </span>
  );
}
