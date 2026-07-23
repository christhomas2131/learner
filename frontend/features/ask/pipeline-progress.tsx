"use client";

import dynamic from "next/dynamic";
import { Check, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/use-reduced-motion";

// Canvas component: client-only (paints on the client after theme resolves).
const ThinkingOrb = dynamic(() => import("thinking-orbs").then((m) => m.ThinkingOrb), {
  ssr: false,
});

type OrbState = "working" | "searching" | "solving" | "listening" | "composing" | "shaping";

export const STAGES: { key: string; label: string }[] = [
  { key: "VALIDATE_INPUT", label: "Validating question" },
  { key: "RESOLVE_DETERMINISTIC_QUESTION", label: "Checking deterministic resolvers" },
  { key: "RETRIEVE", label: "Retrieving approved sources" },
  { key: "DRAFT", label: "Drafting candidate answer" },
  { key: "EXTRACT_CLAIMS", label: "Extracting atomic claims" },
  { key: "VERIFY_CLAIMS", label: "Verifying claims" },
  { key: "REVISE", label: "Revising unsupported material" },
  { key: "RELEASE_GATE", label: "Applying release gate" },
  { key: "PERSIST_AUDIT", label: "Saving audit record" },
];

// Map each pipeline stage to a hand-tuned thinking-orb animation.
const STAGE_ORB: Record<string, OrbState> = {
  VALIDATE_INPUT: "searching",
  RESOLVE_DETERMINISTIC_QUESTION: "searching",
  RETRIEVE: "searching",
  DRAFT: "composing",
  EXTRACT_CLAIMS: "composing",
  VERIFY_CLAIMS: "solving",
  REVISE: "shaping",
  RELEASE_GATE: "solving",
  PERSIST_AUDIT: "solving",
};

export function PipelineProgress({
  reached,
  activeStage,
  done,
  lastMessage,
}: {
  reached: Set<string>;
  activeStage: string | null;
  done: boolean;
  lastMessage?: string;
}) {
  const reduced = useReducedMotion();
  const orbState: OrbState = activeStage ? (STAGE_ORB[activeStage] ?? "working") : "working";

  return (
    <div
      className="rounded-lg border border-border bg-card p-4"
      role="status"
      aria-live="polite"
      aria-label="Verification pipeline progress"
    >
      <div className="mb-3 flex items-center gap-3">
        <div className="flex size-11 shrink-0 items-center justify-center">
          <ThinkingOrb state={orbState} size={64} theme="auto" paused={reduced}
            style={{ width: 44, height: 44 }} aria-label="Thinking" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium">Verification pipeline</p>
          {lastMessage && <p className="truncate text-xs text-muted-foreground">{lastMessage}</p>}
        </div>
      </div>
      <ol className="flex flex-col gap-1.5">
        {STAGES.map((stage) => {
          const isDone = done || (reached.has(stage.key) && activeStage !== stage.key);
          const isActive = !done && activeStage === stage.key;
          const isReached = reached.has(stage.key);
          return (
            <li
              key={stage.key}
              className={cn(
                "flex items-center gap-2.5 text-sm",
                !isReached && "text-muted-foreground/50",
                isActive && "text-foreground",
              )}
            >
              {isActive ? (
                <Loader2 className="size-4 shrink-0 animate-spin text-primary" aria-hidden />
              ) : isDone && isReached ? (
                <Check className="size-4 shrink-0 text-verified" aria-hidden />
              ) : (
                <Circle className="size-4 shrink-0 opacity-40" aria-hidden />
              )}
              <span>{stage.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
