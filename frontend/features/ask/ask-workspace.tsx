"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { useQueryClient } from "@tanstack/react-query";
import { BorderBeam } from "border-beam";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { Button } from "@/components/ui/button";

const ThinkingOrb = dynamic(() => import("thinking-orbs").then((m) => m.ThinkingOrb), {
  ssr: false,
});
import { answerResponse, type AnswerResponse } from "@/lib/api/schemas";
import { streamAnswer } from "@/lib/api/sse";
import { useAnswer, useQueueItem } from "@/lib/api/hooks";
import { Composer, type AskMode } from "@/features/ask/composer";
import { PipelineProgress } from "@/features/ask/pipeline-progress";
import { AnswerView } from "@/features/ask/answer-view";
import { EvidencePanel } from "@/features/ask/evidence-panel";

interface RunState {
  question: string;
  reached: Set<string>;
  activeStage: string | null;
  lastMessage: string;
  streaming: boolean;
  answer: AnswerResponse | null;
  queueId: string | null;
  error: string | null;
}

const INITIAL: RunState = {
  question: "",
  reached: new Set(),
  activeStage: null,
  lastMessage: "",
  streaming: false,
  answer: null,
  queueId: null,
  error: null,
};

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
  const reduced = useReducedMotion();
  const [run, setRun] = React.useState<RunState>(() => ({
    ...INITIAL,
    answer: initialAnswer ?? null,
  }));
  const [panelOpen, setPanelOpen] = React.useState(true);
  const [selectedCitation, setSelectedCitation] = React.useState<number | null>(null);
  const [tab, setTab] = React.useState("claims");
  const abortRef = React.useRef<AbortController | null>(null);

  // Poll premium queue item; when DONE, load the persisted answer.
  const queue = useQueueItem(run.queueId, !!run.queueId);
  const doneAnswerId = queue.data?.status === "DONE" ? queue.data.answer_id : null;
  const persisted = useAnswer(doneAnswerId);

  React.useEffect(() => {
    if (persisted.data) {
      setRun((r) => ({ ...r, answer: persisted.data!, streaming: false, queueId: null,
        activeStage: null, reached: new Set(persisted.data!.pipeline.completed_stages) }));
    }
  }, [persisted.data]);

  React.useEffect(() => {
    if (queue.data?.status === "FAILED") {
      setRun((r) => ({ ...r, streaming: false, error: queue.data?.error ?? "Worker failed" }));
    }
  }, [queue.data?.status, queue.data?.error]);

  async function ask(question: string, mode: AskMode) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSelectedCitation(null);
    setRun({ ...INITIAL, question, streaming: true });

    try {
      await streamAnswer(
        { question, mode, session_id: sessionId ?? null },
        (ev) => {
          setRun((r) => {
            const reached = new Set(r.reached);
            let activeStage = r.activeStage;
            let lastMessage = r.lastMessage;
            const data = ev.data as Record<string, unknown>;
            if (ev.event === "pipeline_stage" && data.stage) {
              activeStage = String(data.stage);
              reached.add(activeStage);
              lastMessage = String(data.message ?? "");
            } else if (["source_retrieved", "draft_created", "claim_verification",
              "revision_started", "release_gate"].includes(ev.event)) {
              lastMessage = String(data.message ?? r.lastMessage);
            } else if (ev.event === "completed") {
              const parsed = answerResponse.safeParse(ev.data);
              return {
                ...r,
                streaming: false,
                activeStage: null,
                answer: parsed.success ? parsed.data : r.answer,
                error: parsed.success ? null : "Malformed response from server.",
              };
            } else if (ev.event === "queued") {
              return { ...r, queueId: String(data.queue_id), lastMessage:
                "Queued for a Claude Code worker. Answer appears when a worker processes it." };
            } else if (ev.event === "failed") {
              return { ...r, streaming: false, error: String(data.message ?? "Failed") };
            }
            return { ...r, reached, activeStage, lastMessage };
          });
        },
        controller.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setRun((r) => ({ ...r, streaming: false, error: (e as Error).message }));
        toast.error("Could not reach the backend.");
      }
    } finally {
      qc.invalidateQueries({ queryKey: ["sessions"] });
    }
  }

  function cancel() {
    abortRef.current?.abort();
    setRun((r) => ({ ...r, streaming: false, queueId: null, activeStage: null }));
  }

  function onCite(n: number) {
    setSelectedCitation(n);
    setPanelOpen(true);
    setTab("claims");
  }

  const showRun = run.streaming || run.answer || run.error;
  const waitingPremium = !!run.queueId && !run.answer;

  return (
    <div className="flex h-full min-h-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 p-5 md:p-8">
          {!showRun && (
            <div className="pt-4">
              <h1 className="text-2xl font-semibold tracking-tight">Ask with confidence</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Answers come only from your approved materials. Every claim is checked against a
                cited quotation, and the system abstains when the evidence isn&apos;t there.
              </p>
            </div>
          )}

          <Composer onSubmit={ask} onCancel={cancel} streaming={run.streaming} autoFocus={!sessionId}
            compact={!!showRun} />

          {!showRun && suggestions && suggestions.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium text-muted-foreground">Try asking</p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s, "grounded")}
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
              <ThinkingOrb state="working" size={64} theme="auto" paused={reduced}
                style={{ width: 40, height: 40 }} aria-label="Waiting for a Claude Code worker" />
              <span>{run.lastMessage}</span>
            </div>
          ) : (
            run.streaming && (
              <BorderBeam size="md" colorVariant="ocean" theme="auto" active={!reduced}
                borderRadius={12}>
                <PipelineProgress reached={run.reached} activeStage={run.activeStage}
                  done={false} lastMessage={run.lastMessage} />
              </BorderBeam>
            )
          )}

          {run.error && (
            <div className="rounded-lg border border-error/40 bg-error-subtle p-4 text-sm text-error">
              {run.error}
            </div>
          )}

          {run.answer && !run.streaming && (
            <AnswerView answer={run.answer} onCite={onCite}
              onRetry={() => ask(run.answer!.question, "grounded")} />
          )}
        </div>
      </div>

      {run.answer && (
        <>
          <aside
            className={cn(
              "hidden shrink-0 border-l border-border bg-subtle transition-[width] lg:block",
              panelOpen ? "w-[420px]" : "w-0 overflow-hidden",
            )}
          >
            {panelOpen && (
              <EvidencePanel answer={run.answer} selectedCitation={selectedCitation}
                tab={tab} onTabChange={setTab} />
            )}
          </aside>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setPanelOpen((o) => !o)}
            className="fixed bottom-6 right-6 hidden lg:flex"
            aria-label={panelOpen ? "Hide evidence panel" : "Show evidence panel"}
          >
            {panelOpen ? <PanelRightClose className="size-4" /> : <PanelRightOpen className="size-4" />}
          </Button>
        </>
      )}
    </div>
  );
}
