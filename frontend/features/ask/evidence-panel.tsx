"use client";

import * as React from "react";
import { BookOpenText, Copy } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/misc";
import { SourceViewer } from "@/features/ask/source-viewer";
import { STAGES } from "@/features/ask/pipeline-progress";
import { TOP_LEVEL_STATUS } from "@/lib/verification";
import type { AnswerResponse, ClaimOut } from "@/lib/api/schemas";

const STAGE_LABEL: Record<string, string> = Object.fromEntries(STAGES.map((s) => [s.key, s.label]));

interface ViewerTarget {
  sourceId: string;
  title?: string;
  quotation: string;
}

export function EvidencePanel({
  answer,
  selectedCitation,
  tab,
  onTabChange,
  headerClassName,
}: {
  answer: AnswerResponse;
  selectedCitation: number | null;
  tab: string;
  onTabChange: (t: string) => void;
  /** Extra classes on the tab header — used to clear the sheet's close button. */
  headerClassName?: string;
}) {
  const claimRefs = React.useRef<Record<string, HTMLDivElement | null>>({});
  const [viewer, setViewer] = React.useState<ViewerTarget | null>(null);
  const titleFor = (sid: string) => answer.sources.find((s) => s.source_id === sid)?.title;
  const onView = (sourceId: string, quotation: string) =>
    setViewer({ sourceId, quotation, title: titleFor(sourceId) });

  const highlightedClaimId = React.useMemo(() => {
    if (selectedCitation == null) return null;
    return (
      answer.claims.find((c) =>
        c.citations.some((cit) => cit.citation_number === selectedCitation),
      )?.claim_id ?? null
    );
  }, [selectedCitation, answer.claims]);

  React.useEffect(() => {
    const el = highlightedClaimId ? claimRefs.current[highlightedClaimId] : null;
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      // Move focus so keyboard / screen-reader users perceive the citation → claim jump.
      el.focus({ preventScroll: true });
    }
  }, [highlightedClaimId, selectedCitation]);

  return (
    <>
      <Tabs value={tab} onValueChange={onTabChange} className="flex h-full flex-col">
        <div className={cn("border-b border-border p-3", headerClassName)}>
          <TabsList className="w-full justify-between">
            <TabsTrigger value="claims">Claims</TabsTrigger>
            <TabsTrigger value="sources">Sources</TabsTrigger>
            <TabsTrigger value="trace">Trace</TabsTrigger>
          </TabsList>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-4">
            <TabsContent value="claims" className="mt-0 space-y-3">
              {answer.status === "CONTRADICTION" && answer.contradiction_detail && (
                <div className="rounded-md border border-contradiction/30 bg-contradiction-subtle p-3 text-sm text-contradiction">
                  {answer.contradiction_detail}
                </div>
              )}
              {answer.claims.length === 0 && <Empty>No claims were extracted.</Empty>}
              {answer.claims.map((c) => (
                <ClaimCard
                  key={c.claim_id}
                  claim={c}
                  onView={onView}
                  highlighted={c.claim_id === highlightedClaimId}
                  ref={(el) => {
                    claimRefs.current[c.claim_id] = el;
                  }}
                />
              ))}
            </TabsContent>

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

            {/* Trace = the full provenance record: pipeline run + audit identity. */}
            <TabsContent value="trace" className="mt-0 space-y-3 text-sm">
              <div className="space-y-2">
                <Row label="Status" value={TOP_LEVEL_STATUS[answer.status].label} />
                <Row label="Attempts" value={String(answer.pipeline.attempts)} />
                <Row label="Duration" value={`${answer.pipeline.duration_ms} ms`} />
                <Row label="Provider" value={answer.pipeline.provider} />
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Completed stages</p>
                <div className="flex flex-wrap gap-1">
                  {answer.pipeline.completed_stages.map((st) => (
                    <Badge key={st} variant="outline">
                      {STAGE_LABEL[st] ?? st}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="space-y-2 border-t border-border pt-3">
                <Row label="Request ID" value={answer.request_id} mono copyable />
                <Row label="Audit ID" value={answer.audit_id ?? "—"} mono copyable />
                <Row label="Model" value={answer.pipeline.model_identifier ?? "deterministic"} />
                <Row label="Created" value={answer.created_at} mono />
                <p className="pt-1 text-xs text-muted-foreground">
                  Only safe metadata is shown. No hidden prompts, keys, or model reasoning.
                </p>
              </div>
            </TabsContent>
          </div>
        </ScrollArea>
      </Tabs>
      <SourceViewer
        sourceId={viewer?.sourceId ?? null}
        sourceTitle={viewer?.title}
        quotation={viewer?.quotation}
        open={!!viewer}
        onOpenChange={(o) => !o && setViewer(null)}
      />
    </>
  );
}

const ClaimCard = React.forwardRef<
  HTMLDivElement,
  { claim: ClaimOut; highlighted?: boolean; onView?: (sourceId: string, quotation: string) => void }
>(({ claim, highlighted, onView }, ref) => (
  <div
    ref={ref}
    tabIndex={-1}
    className={cn(
      "rounded-md border border-border p-3 transition-shadow focus:outline-none",
      highlighted && "ring-2 ring-ring",
    )}
  >
    <div className="flex items-start justify-between gap-2">
      <p className="text-sm font-medium leading-snug">{claim.text}</p>
    </div>
    <div className="mt-2 flex items-center gap-2">
      <StatusBadge status={claim.status} kind="claim" size="sm" />
      <Tooltip>
        <TooltipTrigger asChild>
          <span>
            <Badge variant="outline" className="cursor-help">
              {claim.material ? "material" : "supporting"}
            </Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-56">
          {claim.material
            ? "Material: this claim affects the verdict and must be supported for the answer to be released."
            : "Supporting: contextual detail; it is checked but does not by itself decide the verdict."}
        </TooltipContent>
      </Tooltip>
    </div>
    {claim.evidence.map((e, i) => (
      <blockquote
        key={i}
        className="mt-2 border-l-2 border-primary/40 bg-muted/50 px-3 py-1.5 text-sm text-muted-foreground"
      >
        “{e.quotation}”
        <span className="mt-1 flex items-center justify-between text-xs opacity-70">
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="cursor-help underline decoration-dotted underline-offset-2">
                match {e.retrieval_score.toFixed(2)}
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-56">
              Retrieval similarity (0–1): how closely this passage matched the question. It is not a
              confidence score for the answer.
            </TooltipContent>
          </Tooltip>
          {onView && (
            <button
              onClick={() => onView(e.source_id, e.quotation)}
              className="inline-flex items-center gap-1 text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <BookOpenText className="size-3" /> view in source
            </button>
          )}
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

function Row({
  label,
  value,
  mono,
  copyable,
}: {
  label: string;
  value: string;
  mono?: boolean;
  copyable?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="flex items-center gap-1.5 text-right">
        <span className={cn(mono && "font-mono text-xs")}>{value}</span>
        {copyable && value && value !== "—" && (
          <button
            onClick={() => {
              navigator.clipboard.writeText(value);
              toast.success(`${label} copied`);
            }}
            className="rounded text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`Copy ${label}`}
          >
            <Copy className="size-3" />
          </button>
        )}
      </span>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-8 text-center text-sm text-muted-foreground">{children}</p>;
}
