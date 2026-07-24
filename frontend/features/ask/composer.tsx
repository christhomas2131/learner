"use client";

import * as React from "react";
import { ArrowUp, ShieldCheck, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useWorkerStatus } from "@/lib/api/hooks";

export type AskMode = "grounded" | "premium";

const MAX = 4000;

export function Composer({
  onSubmit,
  onCancel,
  streaming,
  autoFocus,
  compact,
  mode: controlledMode,
  onModeChange,
}: {
  onSubmit: (question: string, mode: AskMode) => void;
  onCancel?: () => void;
  streaming: boolean;
  autoFocus?: boolean;
  compact?: boolean;
  /** Controlled selected mode. Falls back to internal state when omitted. */
  mode?: AskMode;
  onModeChange?: (mode: AskMode) => void;
}) {
  const [value, setValue] = React.useState("");
  const [internalMode, setInternalMode] = React.useState<AskMode>("grounded");
  const mode = controlledMode ?? internalMode;
  const setMode = (m: AskMode) => (onModeChange ? onModeChange(m) : setInternalMode(m));
  const { data: worker } = useWorkerStatus();
  const workerOnline = worker?.online ?? false;

  const remaining = MAX - value.length;
  const nearLimit = remaining <= 200;

  function submit() {
    const q = value.trim();
    if (!q || streaming) return;
    onSubmit(q, mode);
  }

  return (
    <div className="rounded-lg border border-border bg-card shadow-sm">
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value.slice(0, MAX))}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="Ask a question about your approved materials…"
        aria-label="Question"
        autoFocus={autoFocus}
        className={cn("border-0 shadow-none focus-visible:ring-0", compact ? "min-h-16" : "min-h-28")}
      />
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border p-2">
        <div className="flex items-center gap-1" role="group" aria-label="Answer mode">
          <ModeButton
            active={mode === "grounded"}
            onClick={() => setMode("grounded")}
            icon={<ShieldCheck className="size-3.5" />}
            label="Grounded"
            tip="Instant answer assembled from exact source quotes. No model, fully deterministic."
          />
          <ModeButton
            active={mode === "premium"}
            onClick={() => setMode("premium")}
            icon={<Sparkles className="size-3.5" />}
            label="Premium"
            tip="Fluent answer drafted + verified by a running Claude Code worker session. Same evidence gate."
          />
          <span
            className="ml-1 flex items-center gap-1 text-[11px] text-muted-foreground"
            title={workerOnline ? "Claude Code worker online" : "No Claude Code worker running"}
          >
            <span
              className={cn("size-1.5 rounded-full", workerOnline ? "bg-verified" : "bg-muted-foreground/40")}
            />
            {workerOnline ? "worker online" : "no worker"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Submit hint is discoverable; ⌘/Ctrl+Enter also submits. */}
          <span className={cn("text-xs tabular-nums", nearLimit ? "font-medium text-foreground" : "text-muted-foreground")}>
            {value.length}/{MAX}
          </span>
          {/* Coarse announcement: at most two distinct messages, never a
              per-keystroke count. */}
          <span className="sr-only" role="status" aria-live="polite">
            {remaining <= 0 ? "Character limit reached." : nearLimit ? "Approaching character limit." : ""}
          </span>
          {streaming && onCancel ? (
            <Button variant="outline" size="sm" onClick={onCancel}>
              <X className="size-4" /> Cancel
            </Button>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  onClick={submit}
                  disabled={!value.trim()}
                  aria-label="Ask"
                  className="rounded-full"
                >
                  <ArrowUp className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Ask · ⌘↵</TooltipContent>
            </Tooltip>
          )}
        </div>
      </div>
      {mode === "premium" && !workerOnline && (
        <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
          No Claude Code worker is running — premium questions will queue until one is. Grounded
          answers work right now.
        </p>
      )}
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  icon,
  label,
  tip,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  tip: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          aria-pressed={active}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
            active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted",
          )}
        >
          {icon}
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent>{tip}</TooltipContent>
    </Tooltip>
  );
}
