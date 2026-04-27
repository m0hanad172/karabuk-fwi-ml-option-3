"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Download,
  HelpCircle,
  Loader2,
  Play,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorAlert } from "@/components/ui/error-alert";
import { useApi } from "@/hooks/use-api";
import { api, type PredictionResult } from "@/lib/api";
import { formatIstanbulTime } from "@/lib/time";
import { cn } from "@/lib/utils";

/**
 * Risk Decision — triggers a full pipeline run and shows the resulting
 * operational decision. Layout has been restyled to the enterprise design
 * system; all API bindings, run_type semantics, and Istanbul-time formatting
 * are unchanged from the previous implementation.
 */
export function RiskDecision() {
  const latest = useApi(() => api.getLatestPrediction(), [], 60_000);
  const [manualResult, setManualResult] = useState<PredictionResult | null>(
    null,
  );
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const p = manualResult ?? latest.data;
  const isHighRisk = p?.high_risk_flag === 1;

  async function handleManualCheck() {
    setRunning(true);
    setError(null);
    try {
      const result = await api.runManualCheck();
      setManualResult(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Manual check failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Manual trigger panel */}
      <div className="ent-card p-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="min-w-0">
            <p className="ent-eyebrow">Operator Action</p>
            <h3 className="font-display text-lg font-semibold leading-none mt-1">
              Manual Risk Check
            </h3>
            <p className="text-sm text-muted-foreground mt-2 max-w-xl">
              Triggers a full Stacked v3 pipeline run with fresh model-input
              weather. This is an operational run — it is eligible to influence
              the drone launch policy and will appear on Overview.
            </p>
          </div>
          <div className="flex flex-col items-start md:items-end gap-2 shrink-0">
            <Button onClick={handleManualCheck} disabled={running}>
              {running ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Running pipeline...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Run Manual Check
                </>
              )}
            </Button>
          </div>
        </div>
        {error && (
          <div className="mt-4">
            <ErrorAlert
              title="Manual check failed"
              message={error}
              onRetry={handleManualCheck}
              compact
            />
          </div>
        )}
        {latest.error && !manualResult && !latest.data && (
          <div className="mt-4">
            <ErrorAlert
              title="Could not load latest operational run"
              message={latest.error}
              onRetry={latest.refetch}
              compact
            />
          </div>
        )}
      </div>

      {/* Decision result */}
      {p ? (
        <>
          <div className="grid md:grid-cols-3 gap-4">
            <DecisionTile
              eyebrow="Predicted FWI"
              value={p.predicted_fwi?.toFixed(1) ?? "—"}
              caption={
                p.thresholds?.high_threshold != null
                  ? `High threshold ${p.thresholds.high_threshold}`
                  : "Stage 1 regression"
              }
              tone={isHighRisk ? "danger" : "success"}
            />
            <ProbabilityTile
              probability={p.high_risk_probability ?? 0}
            />
            <DecisionBadgeTile highRisk={isHighRisk} />
          </div>

          {/* Why this decision? — plain-English operator-friendly summary */}
          <WhyThisDecisionCard result={p} />

          {/* Decision explanation (raw reason_code from the pipeline) */}
          <div className="ent-card p-5 space-y-4">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <p className="ent-eyebrow">Stage 2 Classifier</p>
                <h3 className="font-display text-lg font-semibold leading-none mt-1">
                  Decision Explanation
                </h3>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => downloadDecisionBrief(p)}
                aria-label="Download decision brief as Markdown"
              >
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Download brief (.md)
              </Button>
            </div>
            <p className="text-sm leading-relaxed">{p.decision_reason}</p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t">
              <MetaCell label="Run ID" value={p.run_id} mono />
              <MetaCell label="Run Type" value={p.run_type} />
              <MetaCell label="Target Date" value={p.target_date} mono />
              <MetaCell
                label="Run Time"
                value={formatIstanbulTime(p.run_timestamp)}
                mono
              />
            </div>

            {p.thresholds && (
              <div className="flex flex-wrap gap-2 pt-1">
                <Badge
                  variant="outline"
                  className="text-[10px] uppercase tracking-wider"
                >
                  High ≥ {p.thresholds.high_threshold}
                </Badge>
                <Badge
                  variant="outline"
                  className="text-[10px] uppercase tracking-wider"
                >
                  Near ≥ {p.thresholds.near_threshold}
                </Badge>
                <Badge
                  variant="outline"
                  className="text-[10px] uppercase tracking-wider"
                >
                  Prob ≥ {p.thresholds.probability_threshold}
                </Badge>
              </div>
            )}
          </div>
        </>
      ) : (
        !latest.loading && (
          <div className="ent-card p-8 text-center">
            <p className="text-sm text-muted-foreground">
              No operational predictions yet. Run a manual check to see
              results.
            </p>
          </div>
        )
      )}
    </div>
  );
}

// ---------- Tiles -----------------------------------------------------------

function DecisionTile({
  eyebrow,
  value,
  caption,
  tone,
}: {
  eyebrow: string;
  value: string;
  caption: string;
  tone: "danger" | "success" | "neutral";
}) {
  const accent =
    tone === "danger"
      ? "var(--destructive)"
      : tone === "success"
        ? "var(--success)"
        : "var(--primary)";
  return (
    <div className="ent-card px-5 py-5 flex flex-col justify-between min-h-[148px]">
      <div className="flex items-center justify-between">
        <p className="ent-eyebrow">{eyebrow}</p>
        <span
          aria-hidden
          className="ent-status-dot"
          style={{ background: accent }}
        />
      </div>
      <p className="ent-kpi-value font-mono-ent mt-2">{value}</p>
      <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
        {caption}
      </p>
    </div>
  );
}

function ProbabilityTile({ probability }: { probability: number }) {
  const pct = Math.max(0, Math.min(probability, 1));
  const accent =
    pct >= 0.5
      ? "var(--destructive)"
      : pct >= 0.1
        ? "var(--warning)"
        : "var(--success)";
  return (
    <div className="ent-card px-5 py-5 flex flex-col justify-between min-h-[148px]">
      <div className="flex items-center justify-between">
        <p className="ent-eyebrow">High Risk Probability</p>
        <span
          aria-hidden
          className="ent-status-dot"
          style={{ background: accent }}
        />
      </div>
      <p className="ent-kpi-value font-mono-ent mt-2">
        {(pct * 100).toFixed(1)}%
      </p>
      <div
        className="mt-3 h-2 w-full rounded-full overflow-hidden"
        style={{ background: "var(--muted)" }}
        aria-hidden
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct * 100}%`, background: accent }}
        />
      </div>
    </div>
  );
}

function DecisionBadgeTile({ highRisk }: { highRisk: boolean }) {
  return (
    <div
      className={cn(
        "ent-card px-5 py-5 flex flex-col justify-between min-h-[148px]",
      )}
      style={{
        borderColor: highRisk
          ? "rgba(220, 38, 38, 0.35)"
          : "rgba(22, 163, 74, 0.35)",
        background: highRisk
          ? "rgba(220, 38, 38, 0.04)"
          : "rgba(22, 163, 74, 0.04)",
      }}
    >
      <p className="ent-eyebrow">Decision</p>
      <div className="flex items-center gap-3 mt-2">
        <span
          aria-hidden
          className="flex h-10 w-10 items-center justify-center rounded-md"
          style={{
            background: highRisk ? "var(--destructive)" : "var(--success)",
            color: "#FFFFFF",
          }}
        >
          {highRisk ? (
            <AlertTriangle className="h-5 w-5" />
          ) : (
            <CheckCircle2 className="h-5 w-5" />
          )}
        </span>
        <div>
          <p
            className="font-display text-xl font-semibold leading-none"
            style={{
              color: highRisk ? "var(--destructive)" : "var(--success)",
            }}
          >
            {highRisk ? "HIGH RISK" : "NORMAL"}
          </p>
          <p className="text-[11px] text-muted-foreground mt-1">
            Stage 2 classifier verdict
          </p>
        </div>
      </div>
    </div>
  );
}

// ---------- Why this decision? --------------------------------------------

/**
 * Operator-friendly plain-English summary of the stacked decision.
 *
 * All content is derived from the same PredictionResult the API returned —
 * no new math, no invented precision, no rounding beyond one decimal for
 * the display numbers the rest of the tab already uses.
 */
function WhyThisDecisionCard({ result }: { result: PredictionResult }) {
  const {
    predicted_fwi,
    high_risk_probability,
    high_risk_flag,
    thresholds,
  } = result;
  const highThr = thresholds?.high_threshold;
  const nearThr = thresholds?.near_threshold;
  const probThr = thresholds?.probability_threshold;

  const fwiAboveHigh =
    highThr != null && predicted_fwi != null ? predicted_fwi >= highThr : false;
  const fwiInGreyZone =
    nearThr != null &&
    highThr != null &&
    predicted_fwi != null &&
    predicted_fwi >= nearThr &&
    predicted_fwi < highThr;
  const probAboveThr =
    probThr != null && high_risk_probability != null
      ? high_risk_probability >= probThr
      : false;

  const isHigh = high_risk_flag === 1;

  // Which branch of the stacked rule fired?
  let branch: string;
  if (isHigh && fwiAboveHigh) {
    branch =
      "HIGH RISK triggered directly by Stage 1 — predicted FWI is at or above the high threshold.";
  } else if (isHigh && fwiInGreyZone && probAboveThr) {
    branch =
      "HIGH RISK triggered by the Stage 2 safety classifier — predicted FWI sits in the grey zone and the classifier's probability cleared the rescue threshold.";
  } else if (isHigh) {
    branch =
      "HIGH RISK triggered by the stacked rule. See the thresholds below.";
  } else {
    branch =
      "NORMAL — predicted FWI is below the high threshold and the safety classifier did not rescue it into high risk.";
  }

  // One-line natural-language verdict.
  let verdict: string;
  if (isHigh && fwiAboveHigh) {
    verdict =
      "Fire-weather conditions are expected to be dangerous. Both the regression model and the safety rule point to elevated risk.";
  } else if (isHigh) {
    verdict =
      "Fire-weather conditions are borderline, and the safety classifier lifted the call to high risk as a precaution.";
  } else if (fwiInGreyZone) {
    verdict =
      "Fire-weather conditions are in the grey zone, but the safety classifier did not see enough signal to escalate. Treat as normal with vigilance.";
  } else {
    verdict =
      "Fire-weather conditions are well below the high-risk threshold. The safety classifier agrees.";
  }

  return (
    <div
      className="ent-card p-5 space-y-4"
      style={{
        borderColor: isHigh
          ? "rgba(220, 38, 38, 0.35)"
          : "rgba(7, 44, 44, 0.18)",
      }}
    >
      <div className="flex items-center gap-2">
        <HelpCircle
          className="h-4 w-4"
          style={{
            color: isHigh ? "var(--destructive)" : "var(--primary)",
          }}
          aria-hidden
        />
        <div>
          <p className="ent-eyebrow">Operator Summary</p>
          <h3 className="font-display text-lg font-semibold leading-none mt-1">
            Why this decision?
          </h3>
        </div>
      </div>

      <p className="text-sm leading-relaxed">{verdict}</p>

      <ul className="space-y-2 text-[13px] leading-relaxed">
        <ComparisonRow
          label="Predicted FWI vs high threshold"
          fact={
            highThr != null && predicted_fwi != null
              ? `${predicted_fwi.toFixed(1)} vs ${highThr} — ${
                  fwiAboveHigh ? "at or above" : "below"
                }`
              : "not available"
          }
          tone={fwiAboveHigh ? "danger" : "success"}
        />
        <ComparisonRow
          label="Predicted FWI vs grey zone"
          fact={
            nearThr != null && highThr != null && predicted_fwi != null
              ? fwiInGreyZone
                ? `in the grey zone (${nearThr} ≤ ${predicted_fwi.toFixed(1)} < ${highThr})`
                : predicted_fwi < nearThr
                  ? `below the grey zone (< ${nearThr})`
                  : `above the grey zone (≥ ${highThr})`
              : "not available"
          }
          tone={fwiInGreyZone ? "warning" : "neutral"}
        />
        <ComparisonRow
          label="High-risk probability vs threshold"
          fact={
            probThr != null && high_risk_probability != null
              ? `${(high_risk_probability * 100).toFixed(1)}% vs ${(probThr * 100).toFixed(0)}% — ${
                  probAboveThr ? "at or above" : "below"
                }`
              : "not available"
          }
          tone={probAboveThr ? "danger" : "success"}
        />
      </ul>

      <div className="pt-3 border-t">
        <p className="ent-eyebrow mb-1.5">How this was decided</p>
        <p className="text-sm leading-relaxed">{branch}</p>
      </div>
    </div>
  );
}

function ComparisonRow({
  label,
  fact,
  tone,
}: {
  label: string;
  fact: string;
  tone: "danger" | "warning" | "success" | "neutral";
}) {
  const accent =
    tone === "danger"
      ? "var(--destructive)"
      : tone === "warning"
        ? "var(--warning)"
        : tone === "success"
          ? "var(--success)"
          : "var(--muted-foreground)";
  return (
    <li className="flex gap-2">
      <span
        aria-hidden
        className="mt-[7px] h-1.5 w-1.5 rounded-full shrink-0"
        style={{ background: accent }}
      />
      <span>
        <span className="font-medium">{label}:</span>{" "}
        <span className="text-muted-foreground">{fact}</span>
      </span>
    </li>
  );
}

// ---------- Markdown decision-brief download ------------------------------

function downloadDecisionBrief(p: PredictionResult): void {
  const isHigh = p.high_risk_flag === 1;
  const highThr = p.thresholds?.high_threshold;
  const nearThr = p.thresholds?.near_threshold;
  const probThr = p.thresholds?.probability_threshold;

  const fwiAboveHigh =
    highThr != null && p.predicted_fwi != null
      ? p.predicted_fwi >= highThr
      : false;
  const fwiInGreyZone =
    nearThr != null &&
    highThr != null &&
    p.predicted_fwi != null &&
    p.predicted_fwi >= nearThr &&
    p.predicted_fwi < highThr;
  const probAboveThr =
    probThr != null && p.high_risk_probability != null
      ? p.high_risk_probability >= probThr
      : false;

  let branch: string;
  if (isHigh && fwiAboveHigh) {
    branch =
      "HIGH RISK — Stage 1 regression placed predicted FWI at or above the high threshold.";
  } else if (isHigh && fwiInGreyZone && probAboveThr) {
    branch =
      "HIGH RISK — grey-zone call rescued by the Stage 2 safety classifier (probability cleared the rescue threshold).";
  } else if (isHigh) {
    branch = "HIGH RISK — triggered by the stacked rule.";
  } else {
    branch =
      "NORMAL — predicted FWI below the high threshold and no Stage 2 rescue.";
  }

  const lines: string[] = [
    "# Karabük FWI — Decision Brief",
    "",
    `- **Run ID:** \`${p.run_id}\``,
    `- **Run type:** ${p.run_type}`,
    `- **Run timestamp:** ${formatIstanbulTime(p.run_timestamp)}`,
    `- **Target date:** ${p.target_date}`,
    "",
    "## Verdict",
    "",
    `**${isHigh ? "HIGH RISK" : "NORMAL"}**`,
    "",
    "## Numbers",
    "",
    `- Predicted FWI: **${p.predicted_fwi?.toFixed(1) ?? "—"}**`,
    `- High-risk probability: **${
      p.high_risk_probability != null
        ? (p.high_risk_probability * 100).toFixed(1) + "%"
        : "—"
    }**`,
    "",
    "## Thresholds in effect",
    "",
    `- High threshold: ${highThr ?? "—"}`,
    `- Near (grey-zone) threshold: ${nearThr ?? "—"}`,
    `- Probability (rescue) threshold: ${
      probThr != null ? (probThr * 100).toFixed(0) + "%" : "—"
    }`,
    "",
    "## Why this decision?",
    "",
    branch,
    "",
    p.decision_reason ? `> ${p.decision_reason}` : "",
    "",
    "---",
    "",
    "_Generated by the Karabük FWI operational console. All times Europe/Istanbul (TRT)._",
    "",
  ];

  const md = lines.join("\n");
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `decision-brief-${p.target_date}-${p.run_id}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function MetaCell({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | number | undefined;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p className="ent-eyebrow">{label}</p>
      <p
        className={cn(
          "mt-1 text-sm truncate",
          mono && "font-mono-ent",
        )}
        title={value != null ? String(value) : undefined}
      >
        {value ?? "—"}
      </p>
    </div>
  );
}
