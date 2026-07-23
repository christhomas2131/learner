"use client";

import * as React from "react";
import { ArrowUp, Loader2, ShieldCheck, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export type AskMode = "grounded" | "premium";

const MAX = 4000;

export function Composer({
  onSubmit,
  onCancel,
  streaming,
  autoFocus,
  compact,
}: {
  onSubmit: (question: string, mode: AskMode) => void;
  onCancel?: () => void;
  streaming: boolean;
  autoFocus?: boolean;
  compact?: boolean;
}) {
  const [value, setValue] = React.useState("");
  const [mode, setMode] = React.useState<AskMode>("grounded");

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
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground" aria-live="polite">
            {value.length}/{MAX}
          </span>
          {streaming && onCancel ? (
            <Button variant="outline" size="sm" onClick={onCancel}>
              <X className="size-4" /> Cancel
            </Button>
          ) : (
            <Button size="sm" onClick={submit} disabled={!value.trim() || streaming}>
              {streaming ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
              Ask
            </Button>
          )}
        </div>
      </div>
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
