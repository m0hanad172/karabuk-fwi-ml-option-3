"use client";

import { ChevronDown, ChevronUp, History, RefreshCw } from "lucide-react";
import { Fragment, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { api, type RunDetail } from "@/lib/api";
import { formatIstanbulTime } from "@/lib/time";

/**
 * Run History — scrollable audit log of every pipeline run. Rows expand to
 * show the raw decision reason and thresholds for that specific run. API
 * contract, expansion logic, and Istanbul-time formatting are unchanged.
 */
export function RunHistory() {
  const history = useApi(() => api.getRunHistory(100), []);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);

  async function toggleExpand(runId: string) {
    if (expandedId === runId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(runId);
    try {
      const d = await api.getRunDetail(runId);
      setDetail(d);
    } catch {
      setDetail(null);
    }
  }

  const runs = history.data ?? [];

  return (
    <div className="ent-card p-5">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
        <div>
          <p className="ent-eyebrow">Operational Audit</p>
          <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
            <History
              className="h-4 w-4"
              style={{ color: "var(--primary)" }}
            />
            Run History
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            {runs.length} runs recorded · click any row for the underlying
            decision reason.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={history.refetch}>
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          Refresh
        </Button>
      </div>

      {history.error ? (
        <ErrorAlert
          title="Could not load run history"
          message={history.error}
          onRetry={history.refetch}
        />
      ) : history.loading && runs.length === 0 ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : runs.length === 0 ? (
        <div
          className="rounded-md border border-dashed px-4 py-10 text-center text-sm text-muted-foreground"
          style={{ borderColor: "var(--border)" }}
        >
          No runs recorded yet. Once a manual or scheduled run completes
          it will appear here.
        </div>
      ) : (
        <div
          className="rounded-md border overflow-hidden"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="max-h-[600px] overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Time (Istanbul)</TableHead>
                  <TableHead>Target Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">FWI</TableHead>
                  <TableHead className="text-right">Probability</TableHead>
                  <TableHead>Decision</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => {
                  const isHigh = run.high_risk_flag === 1;
                  const isExpanded = expandedId === run.run_id;
                  return (
                    <Fragment key={run.run_id}>
                      <TableRow
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => toggleExpand(run.run_id)}
                      >
                        <TableCell>
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </TableCell>
                        <TableCell className="text-sm font-mono-ent">
                          {formatIstanbulTime(run.run_timestamp)}
                        </TableCell>
                        <TableCell className="text-sm font-mono-ent">
                          {run.target_date}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className="text-[10px] uppercase tracking-wider capitalize"
                          >
                            {run.run_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono-ent text-sm">
                          {run.predicted_fwi?.toFixed(1) ?? "—"}
                        </TableCell>
                        <TableCell className="text-right font-mono-ent text-sm">
                          {run.high_risk_probability != null
                            ? `${(run.high_risk_probability * 100).toFixed(1)}%`
                            : "—"}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={isHigh ? "destructive" : "secondary"}
                            className="text-[10px] uppercase tracking-wider"
                          >
                            <span
                              aria-hidden
                              className="ent-status-dot mr-1.5"
                              style={{
                                background: isHigh
                                  ? "var(--destructive)"
                                  : "var(--success)",
                              }}
                            />
                            {isHigh ? "High" : "Normal"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                      {isExpanded && detail && (
                        <TableRow>
                          <TableCell
                            colSpan={7}
                            style={{ background: "var(--muted)" }}
                          >
                            <div className="p-3 space-y-2 text-sm">
                              <DetailRow
                                label="Run ID"
                                value={detail.run_id}
                                mono
                              />
                              <DetailRow
                                label="Decision Reason"
                                value={detail.decision_reason ?? "—"}
                              />
                              {detail.drone_triggered != null && (
                                <DetailRow
                                  label="Drone Triggered"
                                  value={
                                    detail.drone_triggered ? "Yes" : "No"
                                  }
                                />
                              )}
                              {detail.thresholds && (
                                <DetailRow
                                  label="Thresholds"
                                  value={JSON.stringify(detail.thresholds)}
                                  mono
                                />
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3">
      <span className="ent-eyebrow">{label}</span>
      <span
        className={mono ? "font-mono-ent text-xs break-all" : "text-sm"}
      >
        {value}
      </span>
    </div>
  );
}
