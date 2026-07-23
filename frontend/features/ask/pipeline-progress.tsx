"use client";

import { Check, Loader2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

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
  return (
    <div
      className="rounded-lg border border-border bg-card p-4"
      role="status"
      aria-live="polite"
      aria-label="Verification pipeline progress"
    >
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-medium">Verification pipeline</p>
        {lastMessage && <p className="text-xs text-muted-foreground">{lastMessage}</p>}
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
