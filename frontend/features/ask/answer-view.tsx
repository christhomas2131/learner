"use client";

import * as React from "react";
import { Copy, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { TOP_LEVEL_STATUS } from "@/lib/verification";
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
  const isAbstain = answer.status !== "VERIFIED";

  return (
    <article className="t-reveal rounded-lg border border-border bg-card p-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {answer.status === "VERIFIED" ? (
          <span className="inline-flex items-center gap-2 rounded-md border border-verified/30 bg-verified-subtle px-2.5 py-1 text-sm font-medium text-verified">
            <span className="t-success-check" data-state="in" aria-hidden>
              <svg viewBox="0 0 48 48" width="18" height="18" fill="none" stroke="currentColor"
                strokeWidth="5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 25l7 7 15-16" />
              </svg>
            </span>
            Verified
          </span>
        ) : (
          <StatusBadge status={answer.status} />
        )}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              navigator.clipboard.writeText(answer.answer);
              toast.success("Answer copied");
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

      <p className="mb-4 text-sm text-muted-foreground">{meta.description}</p>

      <div
        className={cn(
          "text-[15px] leading-7",
          isAbstain && "italic text-muted-foreground",
        )}
      >
        {answer.answer
          ? renderWithCitations(answer.answer, onCite)
          : "No answer text."}
      </div>

      {answer.status === "CONTRADICTION" && answer.contradiction_detail && (
        <div className="mt-4 rounded-md border border-contradiction/30 bg-contradiction-subtle p-3 text-sm text-contradiction">
          {answer.contradiction_detail}
        </div>
      )}
    </article>
  );
}
