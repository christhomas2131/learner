"use client";

import * as React from "react";
import { AlertOctagon, Copy, GitCompareArrows, HelpCircle, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { TONE_CLASSES, TOP_LEVEL_STATUS } from "@/lib/verification";
import { buildCitedAnswer } from "@/lib/export-answer";
import type { AnswerResponse } from "@/lib/api/schemas";

/** Render answer text, turning [n] markers into clickable citation chips.
 * Text is rendered as plain text nodes (never dangerouslySetInnerHTML). */
function renderWithCitations(text: string, onCite: (n: number) => void): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /\[(\d+)\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(<span key={key++}>{text.slice(last, m.index)}</span>);
    const n = Number(m[1]);
    parts.push(
      <button
        key={key++}
        onClick={() => onCite(n)}
        className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-accent px-1 align-baseline text-xs font-medium text-accent-foreground hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`Open citation ${n}`}
      >
        {n}
      </button>,
    );
    last = regex.lastIndex;
  }
  if (last < text.length) parts.push(<span key={key++}>{text.slice(last)}</span>);
  return parts;
}

const OUTCOME_ICON = { help: HelpCircle, conflict: GitCompareArrows, alert: AlertOctagon } as const;

/** The determination. Every outcome gets the same structural weight: a
 * tone-marked icon, a full-contrast label and a full-contrast description.
 * A confident abstention must read as authoritative, not as a greyed-out
 * failure — that outcome is the product's whole point. */
function VerdictMark({ status }: { status: AnswerResponse["status"] }) {
  const meta = TOP_LEVEL_STATUS[status];
  const Icon = OUTCOME_ICON[meta.icon as keyof typeof OUTCOME_ICON] ?? HelpCircle;
  return (
    <div
      className={cn(
        "flex size-10 shrink-0 items-center justify-center rounded-md border",
        TONE_CLASSES[meta.tone],
      )}
    >
      {status === "VERIFIED" ? (
        <span className="t-success-check" data-state="in" aria-hidden>
          <svg
            viewBox="0 0 48 48"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M13 25l7 7 15-16" />
          </svg>
        </span>
      ) : (
        <Icon className="size-5" aria-hidden />
      )}
    </div>
  );
}

export function AnswerView({
  answer,
  onCite,
  onRetry,
}: {
  answer: AnswerResponse;
  onCite: (citationNumber: number) => void;
  onRetry?: () => void;
}) {
  const meta = TOP_LEVEL_STATUS[answer.status];

  return (
    <article className="t-reveal rounded-lg border border-border bg-card p-6" aria-label={`${meta.label} answer`}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <VerdictMark status={answer.status} />
          <div className="min-w-0">
            <h2 className="font-display text-lg leading-tight text-foreground">{meta.label}</h2>
            <p className="mt-1 text-sm text-foreground">{meta.description}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              navigator.clipboard.writeText(buildCitedAnswer(answer));
              toast.success("Answer + citations copied");
            }}
          >
            <Copy className="size-4" /> Copy
          </Button>
          {onRetry && (
            <Button variant="ghost" size="sm" onClick={onRetry}>
              <RotateCcw className="size-4" /> Retry
            </Button>
          )}
        </div>
      </header>

      <div className="mt-5 border-t border-border pt-5 text-[15px] leading-7 text-foreground">
        {answer.answer
          ? renderWithCitations(answer.answer, onCite)
          : <span className="text-muted-foreground">No answer text.</span>}
      </div>

      {answer.status === "CONTRADICTION" && answer.contradiction_detail && (
        <div className="mt-4 rounded-md border border-contradiction/30 bg-contradiction-subtle p-3 text-sm text-contradiction">
          {answer.contradiction_detail}
        </div>
      )}
    </article>
  );
}
