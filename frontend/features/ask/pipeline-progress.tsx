"use client";

import { Check, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AskMode } from "@/features/ask/composer";

/** Each stage is owned by either the deterministic engine (Python) or the
 * model. In Grounded mode the model stages never run, so they are hidden
 * rather than shown permanently greyed. In Premium the actor is marked so the
 * product's core claim — the deterministic gate decides, not the model — is
 * visible in the pipeline itself. */
export const STAGES: { key: string; label: string; actor: "engine" | "model" }[] = [
  { key: "VALIDATE_INPUT", label: "Validating question", actor: "engine" },
  { key: "RESOLVE_DETERMINISTIC_QUESTION", label: "Checking deterministic resolvers", actor: "engine" },
  { key: "RETRIEVE", label: "Retrieving approved sources", actor: "engine" },
  { key: "DRAFT", label: "Drafting candidate answer", actor: "model" },
  { key: "EXTRACT_CLAIMS", label: "Extracting atomic claims", actor: "model" },
  { key: "VERIFY_CLAIMS", label: "Verifying claims", actor: "model" },
  { key: "REVISE", label: "Revising unsupported material", actor: "model" },
  { key: "RELEASE_GATE", label: "Applying release gate", actor: "engine" },
  { key: "PERSIST_AUDIT", label: "Saving audit record", actor: "engine" },
];

export function PipelineProgress({
  reached,
  activeStage,
  done,
  lastMessage,
  mode = "grounded",
}: {
  reached: Set<string>;
  activeStage: string | null;
  done: boolean;
  lastMessage?: string;
  mode?: AskMode;
}) {
  const visible = mode === "premium" ? STAGES : STAGES.filter((s) => s.actor === "engine");
  const reachedCount = visible.filter((s) => reached.has(s.key)).length;
  const pct = done ? 100 : Math.round((reachedCount / visible.length) * 100);
  const caption =
    mode === "premium"
      ? "The model drafts and self-checks; the deterministic gate decides."
      : "Fully deterministic — no model runs.";
  const activeLabel = activeStage
    ? (STAGES.find((s) => s.key === activeStage)?.label ?? activeStage)
    : "";

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      {/* Concise live region: announce the current step, not the whole 9-item list. */}
      <span className="sr-only" role="status" aria-live="polite">
        {lastMessage || activeLabel || "Verification in progress"}
      </span>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">Verification pipeline</p>
          <p className="truncate text-xs text-muted-foreground">{lastMessage || caption}</p>
        </div>
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
          {reachedCount}/{visible.length}
        </span>
      </div>

      <div className="mb-3 h-1 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>

      <ol className="flex flex-col gap-1.5">
        {visible.map((stage) => {
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
              {mode === "premium" && (
                <span className="ml-auto text-[10px] uppercase tracking-wide text-muted-foreground">
                  {stage.actor === "model" ? "model" : "python"}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
