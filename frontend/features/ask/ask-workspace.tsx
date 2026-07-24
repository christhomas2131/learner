"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertOctagon, Copy, Loader2, PanelRightClose, PanelRightOpen, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { apiFetch } from "@/lib/api/client";
import { answerResponse, enqueueResponse, type AnswerResponse } from "@/lib/api/schemas";
import { TOP_LEVEL_STATUS } from "@/lib/verification";
import { streamAnswer, streamQueueEvents, type SseEvent } from "@/lib/api/sse";
import { Composer, type AskMode } from "@/features/ask/composer";
import { PipelineProgress } from "@/features/ask/pipeline-progress";
import { AnswerView } from "@/features/ask/answer-view";
import { DiscoveryPanel } from "@/features/ask/discovery-panel";
import { EvidencePanel } from "@/features/ask/evidence-panel";

interface RunState {
  question: string;
  mode: AskMode;
  reached: Set<string>;
  activeStage: string | null;
  lastMessage: string;
  streaming: boolean;
  discovering: boolean;
  answer: AnswerResponse | null;
  queueId: string | null;
  error: string | null;
}

const INITIAL: RunState = {
  question: "",
  mode: "grounded",
  reached: new Set(),
  activeStage: null,
  lastMessage: "",
  streaming: false,
  discovering: false,
  answer: null,
  queueId: null,
  error: null,
};

/** True below the `lg` breakpoint, where the fixed evidence aside cannot show
 * and the evidence must open in a sheet instead. */
function useBelowLg() {
  const [below, setBelow] = React.useState(false);
  React.useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)");
    const sync = () => setBelow(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return below;
}

export function AskWorkspace({
  sessionId,
  initialAnswer,
  suggestions,
}: {
  sessionId?: string;
  initialAnswer?: AnswerResponse | null;
  suggestions?: string[];
}) {
  const qc = useQueryClient();
  const belowLg = useBelowLg();
  const [run, setRun] = React.useState<RunState>(() => ({
    ...INITIAL,
    answer: initialAnswer ?? null,
    question: initialAnswer?.question ?? "",
  }));
  const [mode, setMode] = React.useState<AskMode>("grounded");
  const [panelOpen, setPanelOpen] = React.useState(true);
  const [mobileEvidenceOpen, setMobileEvidenceOpen] = React.useState(false);
  const [selectedCitation, setSelectedCitation] = React.useState<number | null>(null);
  const [tab, setTab] = React.useState("claims");
  const abortRef = React.useRef<AbortController | null>(null);

  async function ask(question: string, askMode: AskMode) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSelectedCitation(null);
    setRun({ ...INITIAL, question, mode: askMode, streaming: true });

    const onEvent = (ev: SseEvent) =>
      setRun((r) => {
        const reached = new Set(r.reached);
        let activeStage = r.activeStage;
        let lastMessage = r.lastMessage;
        const data = (ev.data ?? {}) as Record<string, unknown>;
        if (ev.event === "pipeline_stage" && data.stage) {
          activeStage = String(data.stage);
          reached.add(activeStage);
          lastMessage = String(data.message ?? "");
        } else if (ev.event === "discovering") {
          // Abstained with discovery on: searching the web for candidate sources.
          return {
            ...r, discovering: true, activeStage: null,
            lastMessage: "Searching the web for candidate sources…",
          };
        } else if (
          ["source_retrieved", "draft_created", "claim_verification", "revision_started",
            "release_gate"].includes(ev.event)
        ) {
          lastMessage = String(data.message ?? r.lastMessage);
        } else if (ev.event === "completed") {
          const parsed = answerResponse.safeParse(ev.data);
          return {
            ...r, streaming: false, discovering: false, activeStage: null,
            answer: parsed.success ? parsed.data : r.answer,
            error: parsed.success ? null : "Malformed response from server.",
          };
        } else if (ev.event === "failed") {
          return { ...r, streaming: false, discovering: false, error: String(data.message ?? "Failed") };
        }
        return { ...r, reached, activeStage, lastMessage };
      });

    try {
      if (askMode === "premium") {
        // Enqueue, then stream the worker's live pipeline events over SSE.
        const enq = await apiFetch("/api/v1/answers", enqueueResponse, {
          method: "POST",
          body: { question, mode: "premium", session_id: sessionId ?? null },
        });
        setRun((r) => ({ ...r, queueId: enq.queue_id, lastMessage: "Queued — waiting for a worker…" }));
        await streamQueueEvents(enq.queue_id, onEvent, controller.signal);
      } else {
        await streamAnswer(
          { question, mode: askMode, session_id: sessionId ?? null }, onEvent, controller.signal,
        );
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setRun((r) => ({ ...r, streaming: false, discovering: false, error: (e as Error).message }));
        toast.error("Could not reach the backend.");
      }
    } finally {
      qc.invalidateQueries({ queryKey: ["sessions"] });
    }
  }

  function cancel() {
    abortRef.current?.abort();
    setRun((r) => ({ ...r, streaming: false, discovering: false, queueId: null, activeStage: null }));
  }

  function onCite(n: number) {
    setSelectedCitation(n);
    setTab("claims");
    if (belowLg) setMobileEvidenceOpen(true);
    else setPanelOpen(true);
  }

  const showRun = run.streaming || run.answer || run.error;
  const needsSources = run.answer?.status === "NEEDS_SOURCES";
  // The evidence aside is meaningful only for a real verdict — a NEEDS_SOURCES
  // result has no claims/sources yet (the DiscoveryPanel takes over instead).
  const evidenceReady = !!run.answer && !needsSources;
  // "Waiting for a worker" only until the first live pipeline event arrives;
  // then the normal pipeline progress takes over.
  const waitingPremium = !!run.queueId && !run.answer && !run.error && run.reached.size === 0;

  // Persistent live region: the verdict (and errors) must reach assistive tech,
  // since the pipeline's own live region unmounts when streaming ends.
  const liveMessage = run.error
    ? `Error: ${run.error}`
    : run.answer && !run.streaming
      ? `${TOP_LEVEL_STATUS[run.answer.status].label}. ${TOP_LEVEL_STATUS[run.answer.status].description}`
      : "";

  return (
    <div className="flex h-full min-h-0">
      <p className="sr-only" role="status" aria-live="polite">
        {liveMessage}
      </p>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 p-5 md:p-8">
          {!showRun && (
            <div className="pt-4">
              <h1 className="text-3xl font-semibold tracking-tight">Ask with confidence</h1>
              <p className="measure mt-2 text-sm text-muted-foreground">
                Answers come only from your approved materials. Every claim is checked against a
                cited quotation, and the system abstains when the evidence isn&apos;t there.
              </p>
            </div>
          )}

          <Composer onSubmit={ask} onCancel={cancel} streaming={run.streaming} autoFocus={!sessionId}
            compact={!!showRun} mode={mode} onModeChange={setMode} />

          {!showRun && suggestions && suggestions.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="eyebrow text-muted-foreground">Try asking</p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s, mode)}
                    className="rounded-full border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {run.question && showRun && (
            <p className="text-sm font-medium text-muted-foreground">
              <span className="text-foreground">Q:</span> {run.question}
            </p>
          )}

          {waitingPremium ? (
            <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4 text-sm">
              <Loader2 className="size-4 shrink-0 animate-spin text-primary" aria-hidden />
              <span>{run.lastMessage}</span>
            </div>
          ) : (
            run.streaming && !run.discovering && (
              <PipelineProgress reached={run.reached} activeStage={run.activeStage}
                done={false} lastMessage={run.lastMessage} mode={run.mode} />
            )
          )}

          {run.discovering && (
            <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4 text-sm">
              <Loader2 className="size-4 shrink-0 animate-spin text-primary" aria-hidden />
              <span>Searching the web for candidate sources…</span>
            </div>
          )}

          {run.error && (
            <div className="rounded-lg border border-error/40 bg-error-subtle p-4 text-sm text-error">
              <div className="flex items-start gap-2">
                <AlertOctagon className="mt-0.5 size-4 shrink-0" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">Verification could not complete</p>
                  <p className="mt-1 break-words text-error/90">{run.error}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    {run.question && (
                      <Button variant="outline" size="sm" onClick={() => ask(run.question, run.mode)}>
                        <RotateCcw className="size-4" /> Retry
                      </Button>
                    )}
                    {run.queueId && (
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(run.queueId!);
                          toast.success("Reference copied");
                        }}
                        className="inline-flex items-center gap-1 text-xs text-error/80 hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-label="Copy reference id"
                      >
                        <Copy className="size-3" /> Ref {run.queueId}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {run.answer && !run.streaming && needsSources && (
            <DiscoveryPanel
              question={run.answer.question}
              sessionId={sessionId ?? run.answer.session_id}
              discoveryId={run.answer.discovery_id ?? null}
              candidates={run.answer.candidates ?? []}
              onAnswer={(answer) => {
                setRun((r) => ({ ...r, answer }));
                qc.invalidateQueries({ queryKey: ["sessions"] });
              }}
            />
          )}

          {run.answer && !run.streaming && !needsSources && (
            <AnswerView answer={run.answer} onCite={onCite}
              onRetry={() => ask(run.answer!.question, run.mode)} />
          )}
        </div>
      </div>

      {/* Desktop (lg+): fixed evidence aside + toggle. */}
      {evidenceReady && (
        <>
          <aside
            className={cn(
              "hidden shrink-0 border-l border-border bg-subtle lg:block",
              panelOpen ? "w-[420px]" : "w-0 overflow-hidden",
            )}
          >
            {panelOpen && (
              <EvidencePanel answer={run.answer!} selectedCitation={selectedCitation}
                tab={tab} onTabChange={setTab} />
            )}
          </aside>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setPanelOpen((o) => !o)}
            className="fixed bottom-6 right-6 z-40 hidden lg:flex"
            aria-label={panelOpen ? "Hide evidence panel" : "Show evidence panel"}
          >
            {panelOpen ? <PanelRightClose className="size-4" /> : <PanelRightOpen className="size-4" />}
          </Button>
        </>
      )}

      {/* Below lg: evidence opens in a sheet (citations + this button trigger it). */}
      {evidenceReady && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setMobileEvidenceOpen(true)}
          className="fixed bottom-6 right-6 z-40 shadow-sm lg:hidden"
        >
          <PanelRightOpen className="size-4" /> Evidence
        </Button>
      )}
      {evidenceReady && belowLg && (
        <Sheet open={mobileEvidenceOpen} onOpenChange={setMobileEvidenceOpen}>
          <SheetContent className="p-0">
            <SheetTitle className="sr-only">Evidence</SheetTitle>
            <SheetDescription className="sr-only">
              Sources, claims, and the audit trace for this answer.
            </SheetDescription>
            <div className="h-full overflow-hidden">
              <EvidencePanel answer={run.answer!} selectedCitation={selectedCitation}
                tab={tab} onTabChange={setTab} headerClassName="pr-10" />
            </div>
          </SheetContent>
        </Sheet>
      )}
    </div>
  );
}
