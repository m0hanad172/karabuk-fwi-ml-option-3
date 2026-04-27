"use client";

import { Brain, Clock, Database, Server, Shield, Sliders } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ErrorAlert } from "@/components/ui/error-alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatIstanbulTime } from "@/lib/time";

/**
 * System & Model — operator-facing view of backend health, model
 * metadata, decision thresholds and the APScheduler state.
 *
 * Phase 4 rewrite: this tab was the last piece of the UI still using
 * stock shadcn `Card` primitives and raw Tailwind colour utilities.
 * Every surface now uses the enterprise `ent-card`/eyebrow pattern,
 * `var(--…)` tokens, `font-mono-ent` for numeric/monospace cells, and
 * `ErrorAlert` / `Skeleton` for the failure and loading states.
 *
 * Data bindings are unchanged — this is purely a visual normalisation.
 */
export function SystemModel() {
  const health = useApi(() => api.getHealth(), [], 30_000);
  const model = useApi(() => api.getModelInfo(), []);
  const scheduler = useApi(() => api.getScheduler(), [], 30_000);

  const h = health.data;
  const m = model.data;
  const s = scheduler.data;

  return (
    <div className="space-y-6">
      {/* ---------- Health ---------- */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
          <div>
            <p className="ent-eyebrow">Runtime</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Server
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              System Health
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Live status of Stage 1, Stage 2 and the SQLite audit log.
              Auto-refreshes every 30 seconds.
            </p>
          </div>
          {h && (
            <Badge
              variant={h.status === "healthy" ? "default" : "destructive"}
              className="text-[10px] uppercase tracking-wider self-start md:self-center"
            >
              <span
                aria-hidden
                className="ent-status-dot mr-1.5"
                style={{
                  background:
                    h.status === "healthy"
                      ? "var(--success)"
                      : "var(--destructive)",
                }}
              />
              {h.status}
            </Badge>
          )}
        </div>

        {health.error && !h ? (
          <ErrorAlert
            title="Backend unreachable"
            message={health.error}
            onRetry={health.refetch}
          />
        ) : h ? (
          <>
            <div className="grid sm:grid-cols-3 gap-3">
              <HealthItem label="Stage 1 model" ok={h.stage1_model_loaded} />
              <HealthItem label="Stage 2 model" ok={h.stage2_model_loaded} />
              <HealthItem label="Audit database" ok={h.database_ok} />
            </div>
            <p className="text-[11px] text-muted-foreground mt-4 flex items-center gap-1.5">
              <Clock className="h-3 w-3" aria-hidden />
              Checked{" "}
              <span className="font-mono-ent text-foreground">
                {formatIstanbulTime(h.timestamp)}
              </span>
            </p>
          </>
        ) : (
          <div className="grid sm:grid-cols-3 gap-3">
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
          </div>
        )}
      </div>

      {/* ---------- Model metadata ---------- */}
      <div className="grid md:grid-cols-2 gap-6">
        <ModelCard
          eyebrow="Stage 1"
          title="Regression backbone"
          icon={<Brain className="h-4 w-4" style={{ color: "var(--primary)" }} />}
          loading={model.loading}
          error={model.error}
          onRetry={model.refetch}
        >
          {m && (
            <>
              <MetaLine label="Model" value={m.stage1_model} />
              <MetaLine
                label="Training features"
                value={String(m.n_training_features)}
              />
              {m.stage1_test_metrics && (
                <MetricsTable metrics={m.stage1_test_metrics} />
              )}
            </>
          )}
        </ModelCard>

        <ModelCard
          eyebrow="Stage 2"
          title="Safety classifier"
          icon={
            <Shield
              className="h-4 w-4"
              style={{ color: "var(--secondary)" }}
            />
          }
          loading={model.loading}
          error={model.error}
          onRetry={model.refetch}
        >
          {m && (
            <>
              <MetaLine label="Model" value={m.stage2_model} />
              <MetaLine
                label="Stage 2 input"
                value={m.stage2_input_features.join(", ")}
                mono
              />
              {m.stage2_test_metrics && (
                <MetricsTable metrics={m.stage2_test_metrics} />
              )}
            </>
          )}
        </ModelCard>
      </div>

      {/* ---------- Thresholds ---------- */}
      <div className="ent-card p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="ent-eyebrow">Decision rule</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Sliders
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              Thresholds
            </h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
              The Stacked v3 rule promotes a day to HIGH_RISK when Stage 1 is
              above the high threshold, or when Stage 1 lies in the grey
              zone and Stage 2&apos;s probability clears the rescue bar.
            </p>
          </div>
          <Badge
            variant="outline"
            className="text-[10px] uppercase tracking-wider"
          >
            Static
          </Badge>
        </div>

        {m ? (
          <div className="grid sm:grid-cols-3 gap-3">
            <ThresholdTile
              label="High threshold (FWI)"
              value={m.thresholds.high_threshold}
              hint="Stage 1 ≥ this ⇒ HIGH_RISK"
            />
            <ThresholdTile
              label="Near threshold (FWI)"
              value={m.thresholds.near_threshold}
              hint="Stage 1 in [near, high) ⇒ grey zone"
            />
            <ThresholdTile
              label="Probability threshold"
              value={m.thresholds.probability_threshold}
              hint="Stage 2 ≥ this in grey zone ⇒ rescue"
            />
          </div>
        ) : model.error ? (
          <ErrorAlert
            title="Could not load thresholds"
            message={model.error}
            onRetry={model.refetch}
            compact
          />
        ) : (
          <div className="grid sm:grid-cols-3 gap-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        )}
      </div>

      {/* ---------- Scheduler ---------- */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
          <div>
            <p className="ent-eyebrow">APScheduler</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
              <Database
                className="h-4 w-4"
                style={{ color: "var(--primary)" }}
              />
              Scheduler Status
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              Two scheduled operational slots at 11:00 and 15:00
              Europe/Istanbul. Both are always registered at boot.
            </p>
          </div>
          {s && (
            <Badge
              variant={s.running ? "default" : "secondary"}
              className="text-[10px] uppercase tracking-wider self-start md:self-center"
            >
              <span
                aria-hidden
                className="ent-status-dot mr-1.5"
                style={{
                  background: s.running
                    ? "var(--success)"
                    : "var(--muted-foreground)",
                }}
              />
              {s.running ? "Active" : "Inactive"}
            </Badge>
          )}
        </div>

        {scheduler.error && !s ? (
          <ErrorAlert
            title="Could not read scheduler status"
            message={scheduler.error}
            onRetry={scheduler.refetch}
          />
        ) : s ? (
          s.jobs.length > 0 ? (
            <div
              className="rounded-md border overflow-hidden"
              style={{ borderColor: "var(--border)" }}
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job</TableHead>
                    <TableHead className="text-right">Next run</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {s.jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell className="text-sm">{job.name}</TableCell>
                      <TableCell className="text-right font-mono-ent text-sm">
                        {job.next_run_time
                          ? formatIstanbulTime(job.next_run_time)
                          : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Scheduler is running but no jobs are registered.
            </p>
          )
        ) : (
          <div className="space-y-2">
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- helpers ---------------------------------------------------------

function HealthItem({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div
      className="flex items-center gap-2 rounded-md border px-3 py-2"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <span
        aria-hidden
        className="ent-status-dot"
        style={{
          background: ok ? "var(--success)" : "var(--destructive)",
        }}
      />
      <span className="text-sm">{label}</span>
      <span
        className="ml-auto text-[10px] uppercase tracking-wider font-medium"
        style={{
          color: ok ? "var(--success)" : "var(--destructive)",
        }}
      >
        {ok ? "OK" : "Down"}
      </span>
    </div>
  );
}

function MetaLine({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span
        className={`text-right break-words ${mono ? "font-mono-ent" : "font-medium"}`}
      >
        {value}
      </span>
    </div>
  );
}

function MetricsTable({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div
      className="mt-3 rounded-md border overflow-hidden"
      style={{ borderColor: "var(--border)" }}
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">Metric</TableHead>
            <TableHead className="text-right text-xs">Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(metrics).map(([k, v]) => (
            <TableRow key={k}>
              <TableCell className="font-mono-ent text-xs">
                {k.toUpperCase()}
              </TableCell>
              <TableCell className="text-right font-mono-ent text-xs">
                {typeof v === "number"
                  ? Number.isInteger(v)
                    ? v
                    : v.toFixed(3)
                  : v}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ModelCard({
  eyebrow,
  title,
  icon,
  loading,
  error,
  onRetry,
  children,
}: {
  eyebrow: string;
  title: string;
  icon: React.ReactNode;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="ent-card p-5">
      <div className="mb-4">
        <p className="ent-eyebrow">{eyebrow}</p>
        <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
          {icon}
          {title}
        </h3>
      </div>
      {error ? (
        <ErrorAlert
          title="Could not load model metadata"
          message={error}
          onRetry={onRetry}
          compact
        />
      ) : loading ? (
        <div className="space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : (
        <div className="space-y-2">{children}</div>
      )}
    </div>
  );
}

function ThresholdTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint: string;
}) {
  return (
    <div
      className="rounded-md border px-4 py-3"
      style={{
        borderColor: "var(--border)",
        background: "var(--muted)",
      }}
    >
      <p className="ent-eyebrow">{label}</p>
      <p className="font-display text-3xl font-semibold mt-1 font-mono-ent">
        {value}
      </p>
      <p className="text-[11px] text-muted-foreground mt-1">{hint}</p>
    </div>
  );
}
