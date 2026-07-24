"use client";

// Recharts is heavy; this component is loaded via next/dynamic (ssr:false) from
// progress/page.tsx so it stays out of the route's initial JS bundle.
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TOP_LEVEL_STATUS } from "@/lib/verification";
import type { Analytics, TopLevelStatus } from "@/lib/api/schemas";

const STATUS_COLORS: Record<string, string> = {
  VERIFIED: "var(--verified)",
  INSUFFICIENT_EVIDENCE: "var(--insufficient)",
  CONTRADICTION: "var(--contradiction)",
  // Neutral in the chart: keeps it distinguishable from the contradiction red
  // (both are red verdict tones) and reads as a "failed to complete", not a verdict.
  ERROR: "var(--muted-foreground)",
};

const humanize = (s: string) => s.replace(/_/g, " ").toLowerCase();
const statusLabel = (s: string) => TOP_LEVEL_STATUS[s as TopLevelStatus]?.label ?? humanize(s);

/** The three Recharts visualizations for the Progress page. Rendered client-only. */
export function ProgressCharts({ data }: { data: Analytics }) {
  const statusData = Object.entries(data.status_breakdown)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Outcome breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {statusData.length === 0 ? (
            <Empty />
          ) : (
            <div
              role="img"
              aria-label={`Outcome breakdown: ${statusData
                .map((d) => `${statusLabel(d.name)} ${d.value}`)
                .join(", ")}`}
            >
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85}
                    paddingAngle={2}>
                    {statusData.map((d) => (
                      <Cell key={d.name} fill={STATUS_COLORS[d.name] ?? "var(--muted-foreground)"} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
          <Legend items={statusData.map((d) => ({ name: d.name, color: STATUS_COLORS[d.name] }))} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Sessions over time</CardTitle>
        </CardHeader>
        <CardContent>
          {data.sessions_over_time.length === 0 ? (
            <Empty />
          ) : (
            <div
              role="img"
              aria-label={`Sessions over time across ${data.sessions_over_time.length} day(s)`}
            >
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={data.sessions_over_time}>
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                  <Tooltip content={<ChartTip />} />
                  <Area type="monotone" dataKey="count" stroke="var(--primary)" fill="var(--primary)"
                    fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Source usage by type</CardTitle>
        </CardHeader>
        <CardContent>
          {data.source_usage.length === 0 ? (
            <Empty />
          ) : (
            <div
              role="img"
              aria-label={`Source usage by type: ${data.source_usage
                .map((d) => `${humanize(d.type)} ${d.count}`)
                .join(", ")}`}
            >
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={data.source_usage}>
                  <XAxis dataKey="type" tickFormatter={humanize} tick={{ fontSize: 10 }}
                    stroke="var(--muted-foreground)" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                  <Tooltip content={<ChartTip />} cursor={{ fill: "var(--muted)" }} />
                  <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function Legend({ items }: { items: { name: string; color?: string }[] }) {
  return (
    <div className="mt-3 flex flex-wrap gap-3">
      {items.map((it) => (
        <span key={it.name} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-2.5 rounded-full" style={{ background: it.color }} />
          {statusLabel(it.name)}
        </span>
      ))}
    </div>
  );
}

function ChartTip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name?: string; value?: number | string }[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-md">
      {label !== undefined && <p className="font-medium">{humanize(String(label))}</p>}
      {payload.map((p, i) => (
        <p key={i}>
          {statusLabel(String(p.name))}: <span className="tabular-nums">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

function Empty() {
  return <p className="py-12 text-center text-sm text-muted-foreground">No data yet.</p>;
}
