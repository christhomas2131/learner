"use client";

import dynamic from "next/dynamic";
import { useAnalytics } from "@/lib/api/hooks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { StatusBadge } from "@/components/ui/status-badge";
import { TOP_LEVEL_STATUS } from "@/lib/verification";
import type { TopLevelStatus } from "@/lib/api/schemas";

// Recharts (heavy) loads client-only, after mount — kept out of the route's
// initial JS bundle. See ./progress-charts.
const ProgressCharts = dynamic(
  () => import("./progress-charts").then((m) => m.ProgressCharts),
  {
    ssr: false,
    loading: () => (
      <>
        <Skeleton className="h-[300px]" />
        <Skeleton className="h-[300px]" />
        <Skeleton className="h-[300px]" />
      </>
    ),
  },
);

const humanize = (s: string) => s.replace(/_/g, " ").toLowerCase();
const pct = (v: number) => `${Math.round(v * 100)}%`;

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

  return (
    <Wrap>
      <section aria-label="Educational metrics" className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Questions asked" value={String(data.questions_asked)} />
        <Kpi label="Verified rate" value={pct(data.verified_rate)} tone="text-verified" />
        <Kpi label="Abstention rate" value={pct(data.abstention_rate)} tone="text-insufficient" />
        <Kpi label="Contradiction rate" value={pct(data.contradiction_rate)} tone="text-contradiction" />
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <ProgressCharts data={data} />

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
            <p className="py-12 text-center text-sm text-muted-foreground">No data yet.</p>
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
