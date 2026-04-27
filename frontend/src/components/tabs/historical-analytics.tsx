"use client";

import {
  AlertTriangle,
  BarChart3,
  Calendar,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CardSkeleton, GridSkeleton } from "@/components/card-skeleton";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

/**
 * Historical Analytics — 2012–2025 fire season analytics. Uses the enterprise
 * token palette (deep teal primary, orange accent, warning amber, danger red)
 * across charts so every page feels part of the same product. All API
 * bindings, math and chart data are unchanged.
 */

// Line palette built from enterprise tokens; chosen to stay distinguishable
// while matching the deep-teal / warm-orange / danger-red identity.
const LINE_COLORS = [
  "#072C2C", // primary
  "#FF5F03", // secondary
  "#16A34A", // success
  "#D97706", // warning
  "#DC2626", // destructive
  "#0891B2",
  "#7C3AED",
  "#0D9488",
  "#BE185D",
  "#4F46E5",
  "#4B5563",
  "#EA580C",
  "#059669",
  "#E11D48",
];

const COLOR_PRIMARY = "#072C2C";
const COLOR_DANGER = "#DC2626";
const COLOR_WARNING = "#D97706";
const COLOR_DANGER_SOFT = "#FEE2E2";

export function HistoricalAnalytics() {
  const analytics = useApi(() => api.getAnalytics(), []);

  if (analytics.loading) {
    return (
      <div className="space-y-6">
        <GridSkeleton cards={4} />
        <CardSkeleton lines={5} />
        <CardSkeleton lines={4} />
      </div>
    );
  }

  if (analytics.error) {
    return (
      <div className="ent-card p-8 text-center">
        <p
          className="text-sm"
          style={{ color: "var(--destructive)" }}
        >
          Failed to load analytics: {analytics.error}
        </p>
      </div>
    );
  }

  const data = analytics.data!;
  const years = data.yearly_stats.map((y) => y.year);

  // Pivot year_over_year so each row is {month_name, 2012: fwi, 2013: fwi, ...}
  const seasonalPivot = data.seasonal_profile.map((sp) => {
    const row: Record<string, string | number> = { month_name: sp.month_name };
    for (const entry of data.year_over_year.filter(
      (e) => e.month === sp.month,
    )) {
      row[String(entry.year)] = entry.mean_fwi;
    }
    return row;
  });

  const meanFwiAvg =
    data.yearly_stats.reduce((s, y) => s + y.mean_fwi, 0) /
    data.yearly_stats.length;

  const peak = data.yearly_stats.reduce((a, b) =>
    a.high_risk_days > b.high_risk_days ? a : b,
  );

  // Long-term trend direction: simple OLS slope sign on monthly_series.
  // We only expose the direction + sentence, not the raw slope number —
  // avoiding fake precision while still making the finding honest.
  const trendDirection = monthlyTrendDirection(
    data.monthly_series.map((m) => m.mean_fwi),
  );

  // Seasonal peak month across all years in the seasonal_profile.
  const peakMonth = data.seasonal_profile.reduce((a, b) =>
    (a.mean_fwi ?? 0) >= (b.mean_fwi ?? 0) ? a : b,
  );

  const highRiskShare =
    data.total_records > 0
      ? (data.total_high_risk_days / data.total_records) * 100
      : 0;

  return (
    <div className="space-y-6">
      {/* Key findings — narrative synthesis above the charts */}
      <KeyFindingsCard
        peakYear={peak.year}
        peakHighRiskDays={peak.high_risk_days}
        peakMonthName={peakMonth.month_name}
        peakMonthMeanFwi={peakMonth.mean_fwi}
        trendDirection={trendDirection}
        highRiskShare={highRiskShare}
        startYear={data.dataset_range.start.slice(0, 4)}
        endYear={data.dataset_range.end.slice(0, 4)}
      />

      {/* Summary strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryTile
          eyebrow="Dataset Range"
          icon={<Calendar className="h-4 w-4" />}
          value={`${data.dataset_range.start.slice(0, 4)}–${data.dataset_range.end.slice(0, 4)}`}
          caption={`${data.total_records.toLocaleString()} fire-season days`}
        />
        <SummaryTile
          eyebrow="High-Risk Days"
          icon={<AlertTriangle className="h-4 w-4" />}
          value={data.total_high_risk_days.toString()}
          caption={`FWI ≥ 35 (${((data.total_high_risk_days / data.total_records) * 100).toFixed(1)}%)`}
          tone="danger"
        />
        <SummaryTile
          eyebrow="Mean FWI"
          icon={<TrendingUp className="h-4 w-4" />}
          value={meanFwiAvg.toFixed(1)}
          caption="Average across all years"
        />
        <SummaryTile
          eyebrow="Peak Year"
          icon={<BarChart3 className="h-4 w-4" />}
          value={String(peak.year)}
          caption={`${peak.high_risk_days} high-risk days · max FWI ${peak.max_fwi}`}
        />
      </div>

      {/* Monthly trend */}
      <ChartCard
        eyebrow="Long-Term Trend"
        title="FWI Monthly Trend (2012–2025)"
        icon={<TrendingUp className="h-4 w-4" />}
      >
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={data.monthly_series}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis
              dataKey="date"
              tickFormatter={(v) => String(v).slice(0, 7)}
              interval={5}
              fontSize={11}
            />
            <YAxis fontSize={11} />
            <Tooltip
              labelFormatter={(v) => String(v).slice(0, 7)}
              formatter={(value, name) => [
                Number(value).toFixed(1),
                name === "mean_fwi" ? "Mean FWI" : "Max FWI",
              ]}
            />
            <Legend
              formatter={(v) => (v === "mean_fwi" ? "Mean FWI" : "Max FWI")}
            />
            <ReferenceLine
              y={35}
              stroke={COLOR_DANGER}
              strokeDasharray="5 5"
              label={{
                value: "High Risk (35)",
                fill: COLOR_DANGER,
                fontSize: 11,
              }}
            />
            <Area
              type="monotone"
              dataKey="max_fwi"
              fill={COLOR_DANGER_SOFT}
              stroke="#F87171"
              fillOpacity={0.4}
            />
            <Line
              type="monotone"
              dataKey="mean_fwi"
              stroke={COLOR_PRIMARY}
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
        <p className="text-[11px] text-muted-foreground mt-2 text-center">
          Solid line = monthly mean FWI, shaded area = monthly max FWI. Dashed
          red line marks the high-risk threshold (FWI 35).
        </p>
      </ChartCard>

      {/* Yearly */}
      <ChartCard
        eyebrow="Year Breakdown"
        title="High-Risk Days per Year"
        icon={<AlertTriangle className="h-4 w-4" />}
        rightSlot={
          <Badge
            variant="outline"
            className="text-[10px] uppercase tracking-wider"
          >
            FWI ≥ 35
          </Badge>
        }
      >
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data.yearly_stats}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis dataKey="year" fontSize={11} />
            <YAxis fontSize={11} allowDecimals={false} />
            <Tooltip
              formatter={(value, name) => [
                value,
                name === "high_risk_days" ? "High-Risk Days" : "Mean FWI",
              ]}
            />
            <Legend
              formatter={(v) =>
                v === "high_risk_days" ? "High-Risk Days" : "Mean FWI"
              }
            />
            <Bar dataKey="high_risk_days" fill={COLOR_DANGER} radius={[4, 4, 0, 0]} />
            <Bar dataKey="mean_fwi" fill={COLOR_PRIMARY} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <p className="text-[11px] text-muted-foreground mt-2 text-center">
          Red bars = days per year with FWI ≥ 35. Teal bars = mean FWI for that
          year — context for how dangerous the average day was.
        </p>
      </ChartCard>

      {/* Seasonal profile */}
      <ChartCard
        eyebrow="Seasonality"
        title="Seasonal Profile (May–October Average)"
        icon={<Calendar className="h-4 w-4" />}
      >
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data.seasonal_profile}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis dataKey="month_name" fontSize={11} />
            <YAxis fontSize={11} />
            <Tooltip
              formatter={(value, name) => {
                const labels: Record<string, string> = {
                  mean_fwi: "Mean FWI",
                  max_fwi: "Max FWI",
                  high_risk_days: "High-Risk Days",
                };
                return [
                  typeof value === "number" ? value.toFixed(1) : value,
                  labels[String(name)] || String(name),
                ];
              }}
            />
            <Legend
              formatter={(v) => {
                const labels: Record<string, string> = {
                  mean_fwi: "Mean FWI",
                  max_fwi: "Max FWI",
                  high_risk_days: "High-Risk Days (total)",
                };
                return labels[String(v)] || String(v);
              }}
            />
            <ReferenceLine y={35} stroke={COLOR_DANGER} strokeDasharray="5 5" />
            <Bar
              dataKey="high_risk_days"
              fill="#FCA5A5"
              radius={[4, 4, 0, 0]}
            />
            <Line
              type="monotone"
              dataKey="mean_fwi"
              stroke={COLOR_PRIMARY}
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="max_fwi"
              stroke={COLOR_WARNING}
              strokeWidth={2}
              strokeDasharray="5 5"
            />
          </ComposedChart>
        </ResponsiveContainer>
        <p className="text-[11px] text-muted-foreground mt-2 text-center">
          Averaged across all years. Solid teal = mean FWI by month, dashed
          amber = max FWI, pink bars = total high-risk days in that month.
        </p>
      </ChartCard>

      {/* Year-over-year */}
      <ChartCard
        eyebrow="Comparison"
        title="Year-over-Year Seasonal Comparison"
        icon={<BarChart3 className="h-4 w-4" />}
        rightSlot={
          <Badge
            variant="outline"
            className="text-[10px] uppercase tracking-wider"
          >
            Mean FWI by month
          </Badge>
        }
      >
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={seasonalPivot}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis dataKey="month_name" fontSize={11} />
            <YAxis fontSize={11} />
            <Tooltip formatter={(value) => [Number(value).toFixed(1), "FWI"]} />
            <Legend />
            <ReferenceLine y={35} stroke={COLOR_DANGER} strokeDasharray="5 5" />
            {years.map((year, i) => (
              <Line
                key={year}
                type="monotone"
                dataKey={String(year)}
                stroke={LINE_COLORS[i % LINE_COLORS.length]}
                strokeWidth={year >= 2023 ? 2.5 : 1}
                strokeOpacity={year >= 2023 ? 1 : 0.5}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <p className="text-[11px] text-muted-foreground mt-2 text-center">
          Recent years (2023+) shown with thicker lines. Dashed red line = high-risk threshold (FWI 35).
        </p>
      </ChartCard>
    </div>
  );
}

// ---------- helpers ---------------------------------------------------------

function SummaryTile({
  eyebrow,
  icon,
  value,
  caption,
  tone = "neutral",
}: {
  eyebrow: string;
  icon: React.ReactNode;
  value: string;
  caption: string;
  tone?: "neutral" | "danger";
}) {
  const accent =
    tone === "danger" ? "var(--destructive)" : "var(--primary)";
  return (
    <div className="ent-card px-5 py-5 flex flex-col justify-between min-h-[128px]">
      <div className="flex items-center justify-between">
        <p className="ent-eyebrow">{eyebrow}</p>
        <span style={{ color: accent }} aria-hidden>
          {icon}
        </span>
      </div>
      <p
        className="ent-kpi-value font-mono-ent mt-2"
        style={{ color: accent }}
      >
        {value}
      </p>
      <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
        {caption}
      </p>
    </div>
  );
}

// ---------- Key findings synthesis -----------------------------------------

type TrendDirection = "rising" | "falling" | "flat";

/**
 * Return the direction of a simple least-squares linear fit over the
 * monthly mean-FWI series. We only surface the direction, not the raw
 * slope, to avoid fake precision in the narrative.
 */
function monthlyTrendDirection(values: number[]): TrendDirection {
  const n = values.length;
  if (n < 12) return "flat";
  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumX2 = 0;
  for (let i = 0; i < n; i++) {
    const x = i;
    const y = values[i];
    sumX += x;
    sumY += y;
    sumXY += x * y;
    sumX2 += x * x;
  }
  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return "flat";
  const slope = (n * sumXY - sumX * sumY) / denom;
  // "Flat" if the slope is small relative to the mean — threshold is
  // ~0.5% of the mean per month, i.e. negligible.
  const mean = sumY / n;
  const flatBand = Math.max(0.05, Math.abs(mean) * 0.005);
  if (slope > flatBand) return "rising";
  if (slope < -flatBand) return "falling";
  return "flat";
}

function KeyFindingsCard({
  peakYear,
  peakHighRiskDays,
  peakMonthName,
  peakMonthMeanFwi,
  trendDirection,
  highRiskShare,
  startYear,
  endYear,
}: {
  peakYear: number;
  peakHighRiskDays: number;
  peakMonthName: string;
  peakMonthMeanFwi: number;
  trendDirection: TrendDirection;
  highRiskShare: number;
  startYear: string;
  endYear: string;
}) {
  const trendSentence =
    trendDirection === "rising"
      ? `Monthly mean FWI has trended upward across the ${startYear}–${endYear} window.`
      : trendDirection === "falling"
        ? `Monthly mean FWI has trended downward across the ${startYear}–${endYear} window.`
        : `Monthly mean FWI has stayed broadly flat across the ${startYear}–${endYear} window.`;

  return (
    <section
      className="ent-card p-5"
      aria-labelledby="analytics-key-findings-title"
    >
      <div className="flex items-center gap-2 mb-3">
        <Sparkles
          className="h-4 w-4"
          style={{ color: "var(--secondary)" }}
          aria-hidden
        />
        <div>
          <p className="ent-eyebrow">Narrative</p>
          <h3
            id="analytics-key-findings-title"
            className="font-display text-lg font-semibold leading-none mt-1"
          >
            Key findings
          </h3>
        </div>
      </div>
      <ul className="space-y-2 text-sm leading-relaxed">
        <Finding
          label="Peak fire season"
          fact={`${peakYear} — ${peakHighRiskDays} days with FWI ≥ 35.`}
        />
        <Finding
          label="Riskiest month on average"
          fact={`${peakMonthName}, with a long-run mean FWI of ${peakMonthMeanFwi.toFixed(1)}.`}
        />
        <Finding
          label="Share of high-risk days"
          fact={`${highRiskShare.toFixed(1)}% of all fire-season days in the dataset sat above the high-risk threshold.`}
        />
        <Finding label="Long-term trend" fact={trendSentence} />
      </ul>
      <p className="text-[11px] text-muted-foreground mt-3">
        Derived directly from the aggregated analytics payload — no model
        inference, no interpolation. Numbers round to one decimal.
      </p>
    </section>
  );
}

function Finding({ label, fact }: { label: string; fact: string }) {
  return (
    <li className="flex gap-2">
      <span
        aria-hidden
        className="mt-[7px] h-1.5 w-1.5 rounded-full shrink-0"
        style={{ background: "var(--primary)" }}
      />
      <span>
        <span className="font-medium">{label}:</span>{" "}
        <span className="text-muted-foreground">{fact}</span>
      </span>
    </li>
  );
}

function ChartCard({
  eyebrow,
  title,
  icon,
  rightSlot,
  children,
}: {
  eyebrow: string;
  title: string;
  icon: React.ReactNode;
  rightSlot?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="ent-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="ent-eyebrow">{eyebrow}</p>
          <h3 className="font-display text-lg font-semibold leading-none mt-1 flex items-center gap-2">
            <span style={{ color: "var(--primary)" }} aria-hidden>
              {icon}
            </span>
            {title}
          </h3>
        </div>
        {rightSlot}
      </div>
      {children}
    </div>
  );
}
