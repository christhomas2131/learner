"use client";

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
import { useAnalytics } from "@/lib/api/hooks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { StatusBadge } from "@/components/ui/status-badge";
import { TOP_LEVEL_STATUS } from "@/lib/verification";
import type { TopLevelStatus } from "@/lib/api/schemas";

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

export default function ProgressPage() {
  const { data, isLoading, isError } = useAnalytics();

  if (isError)
    return (
      <Wrap>
        <p className="rounded-md border border-error/40 bg-error-subtle p-4 text-sm text-error">
          Could not load analytics. Is the backend running?
        </p>
      </Wrap>
    );
  if (isLoading || !data)
    return (
      <Wrap>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </Wrap>
    );

  const statusData = Object.entries(data.status_breakdown)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  return (
    <Wrap>
      <section aria-label="Educational metrics" className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Questions asked" value={String(data.questions_asked)} />
        <Kpi label="Verified rate" value={pct(data.verified_rate)} tone="text-verified" />
        <Kpi label="Abstention rate" value={pct(data.abstention_rate)} tone="text-insufficient" />
        <Kpi label="Contradiction rate" value={pct(data.contradiction_rate)} tone="text-contradiction" />
      </section>

      <div className="grid gap-4 md:grid-cols-2">
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

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Operational</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Avg pipeline duration" value={`${Math.round(data.average_duration_ms)} ms`} />
            <Row label="Avg claims per answer" value={data.average_claim_count.toFixed(2)} />
            <Row label="Error rate" value={pct(data.error_rate)} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent activity</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_activity.length === 0 ? (
            <Empty />
          ) : (
            <ul className="divide-y divide-border">
              {data.recent_activity.map((a, i) => (
                <li key={i} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span className="truncate">{a.question}</span>
                  {a.status in TOP_LEVEL_STATUS ? (
                    <StatusBadge status={a.status as TopLevelStatus} size="sm" className="shrink-0" />
                  ) : (
                    <span className="shrink-0 text-xs text-muted-foreground">{humanize(a.status)}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </Wrap>
  );
}

function Wrap({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto h-full w-full max-w-5xl space-y-4 overflow-y-auto scroll-slim p-5 md:p-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Progress</h1>
        <p className="measure mt-2 text-sm text-muted-foreground">
          How your learning sessions resolve. These reflect evidence coverage, not a truth score.
        </p>
      </div>
      {children}
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone ?? ""}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
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

const pct = (v: number) => `${Math.round(v * 100)}%`;
