"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/misc";
import type { AnswerResponse, ClaimOut } from "@/lib/api/schemas";

export function EvidencePanel({
  answer,
  selectedCitation,
  tab,
  onTabChange,
}: {
  answer: AnswerResponse;
  selectedCitation: number | null;
  tab: string;
  onTabChange: (t: string) => void;
}) {
  const claimRefs = React.useRef<Record<string, HTMLDivElement | null>>({});

  const highlightedClaimId = React.useMemo(() => {
    if (selectedCitation == null) return null;
    return (
      answer.claims.find((c) =>
        c.citations.some((cit) => cit.citation_number === selectedCitation),
      )?.claim_id ?? null
    );
  }, [selectedCitation, answer.claims]);

  React.useEffect(() => {
    if (highlightedClaimId && claimRefs.current[highlightedClaimId]) {
      claimRefs.current[highlightedClaimId]?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightedClaimId, selectedCitation]);

  const contradictions = answer.claims.filter((c) => c.status === "CONTRADICTED");

  return (
    <Tabs value={tab} onValueChange={onTabChange} className="flex h-full flex-col">
      <div className="border-b border-border p-3">
        <TabsList className="w-full justify-between">
          <TabsTrigger value="sources">Sources</TabsTrigger>
          <TabsTrigger value="claims">Claims</TabsTrigger>
          <TabsTrigger value="contradictions">Conflicts</TabsTrigger>
          <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
          <TabsTrigger value="audit">Audit</TabsTrigger>
        </TabsList>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4">
          <TabsContent value="sources" className="mt-0 space-y-3">
            {answer.sources.length === 0 && <Empty>No sources were used.</Empty>}
            {answer.sources.map((s) => {
              const citeCount = answer.claims.filter((c) =>
                c.citations.some((ci) => ci.source_id === s.source_id),
              ).length;
              return (
                <div key={s.source_id} className="rounded-md border border-border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium leading-tight">{s.title}</p>
                    {s.approved && <Badge variant="primary">approved</Badge>}
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
                    <Badge variant="outline">{s.source_type}</Badge>
                    {s.author && <span>{s.author}</span>}
                    {s.publication_date && <span>· {s.publication_date}</span>}
                    <span>· {citeCount} citation{citeCount === 1 ? "" : "s"}</span>
                  </div>
                </div>
              );
            })}
          </TabsContent>

          <TabsContent value="claims" className="mt-0 space-y-3">
            {answer.claims.length === 0 && <Empty>No claims were extracted.</Empty>}
            {answer.claims.map((c) => (
              <ClaimCard
                key={c.claim_id}
                claim={c}
                highlighted={c.claim_id === highlightedClaimId}
                ref={(el) => {
                  claimRefs.current[c.claim_id] = el;
                }}
              />
            ))}
          </TabsContent>

          <TabsContent value="contradictions" className="mt-0 space-y-3">
            {contradictions.length === 0 && !answer.contradiction_detail ? (
              <Empty>No contradictions detected.</Empty>
            ) : (
              <>
                {answer.contradiction_detail && (
                  <div className="rounded-md border border-contradiction/30 bg-contradiction-subtle p-3 text-sm text-contradiction">
                    {answer.contradiction_detail}
                  </div>
                )}
                {contradictions.map((c) => (
                  <ClaimCard key={c.claim_id} claim={c} />
                ))}
              </>
            )}
          </TabsContent>

          <TabsContent value="pipeline" className="mt-0 space-y-2 text-sm">
            <Row label="Status" value={answer.status} />
            <Row label="Attempts" value={String(answer.pipeline.attempts)} />
            <Row label="Duration" value={`${answer.pipeline.duration_ms} ms`} />
            <Row label="Provider" value={answer.pipeline.provider} />
            <div className="pt-2">
              <p className="mb-1 text-xs font-medium text-muted-foreground">Completed stages</p>
              <div className="flex flex-wrap gap-1">
                {answer.pipeline.completed_stages.map((st) => (
                  <Badge key={st} variant="outline">
                    {st}
                  </Badge>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="audit" className="mt-0 space-y-2 text-sm">
            <Row label="Request ID" value={answer.request_id} mono />
            <Row label="Audit ID" value={answer.audit_id ?? "—"} mono />
            <Row label="Model" value={answer.pipeline.model_identifier ?? "deterministic"} />
            <Row label="Created" value={answer.created_at} mono />
            <p className="pt-2 text-xs text-muted-foreground">
              Only safe metadata is shown. No hidden prompts, keys, or model reasoning.
            </p>
          </TabsContent>
        </div>
      </ScrollArea>
    </Tabs>
  );
}

const ClaimCard = React.forwardRef<
  HTMLDivElement,
  { claim: ClaimOut; highlighted?: boolean }
>(({ claim, highlighted }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-md border border-border p-3 transition-shadow",
      highlighted && "ring-2 ring-ring",
    )}
  >
    <div className="flex items-start justify-between gap-2">
      <p className="text-sm font-medium leading-snug">{claim.text}</p>
    </div>
    <div className="mt-2 flex items-center gap-2">
      <StatusBadge status={claim.status} kind="claim" size="sm" />
      <Badge variant="outline">{claim.material ? "material" : "supporting"}</Badge>
    </div>
    {claim.evidence.map((e, i) => (
      <blockquote
        key={i}
        className="mt-2 border-l-2 border-primary/40 bg-muted/50 px-3 py-1.5 text-sm text-muted-foreground"
      >
        “{e.quotation}”
        <span className="mt-1 block text-xs opacity-70">
          relevance {e.retrieval_score.toFixed(2)}
        </span>
      </blockquote>
    ))}
    {claim.status === "INSUFFICIENT_EVIDENCE" && (
      <p className="mt-2 text-xs text-muted-foreground">
        Absence of evidence does not prove this claim false.
      </p>
    )}
    {claim.verifier_explanation && (
      <p className="mt-2 text-xs text-muted-foreground">{claim.verifier_explanation}</p>
    )}
  </div>
));
ClaimCard.displayName = "ClaimCard";

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("text-right", mono && "font-mono text-xs")}>{value}</span>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{children}</p>;
}
