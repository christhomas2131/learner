"use client";

import * as React from "react";
import { useMutation } from "@tanstack/react-query";
import { Check, Globe, Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api/client";
import { answerResponse, type AnswerResponse, type CandidateOut } from "@/lib/api/schemas";

const PROVIDER_LABEL: Record<string, string> = {
  wikipedia: "Wikipedia",
  duckduckgo: "DuckDuckGo",
  claude_web: "Claude",
};

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Candidate-source review: the human-in-the-loop gate. The user prunes the
 * web candidates down to the ones they trust; confirming re-fetches each page
 * server-side, adds it as an approved source, and re-runs the verified answer. */
export function DiscoveryPanel({
  question,
  sessionId,
  discoveryId,
  candidates,
  onAnswer,
}: {
  question: string;
  sessionId?: string | null;
  discoveryId?: string | null;
  candidates: CandidateOut[];
  onAnswer: (answer: AnswerResponse) => void;
}) {
  // Default to all selected; the user prunes down before confirming.
  const [selected, setSelected] = React.useState<Set<string>>(
    () => new Set(candidates.map((c) => c.url)),
  );

  const confirm = useMutation({
    mutationFn: (chosen: CandidateOut[]) =>
      apiFetch("/api/v1/discovery/confirm", answerResponse, {
        method: "POST",
        body: {
          question,
          session_id: sessionId ?? null,
          discovery_id: discoveryId ?? null,
          sources: chosen.map((c) => ({ url: c.url, title: c.title })),
        },
      }),
    onSuccess: (answer) => onAnswer(answer),
    onError: (e: unknown) => toast.error((e as Error).message || "Could not add sources."),
  });

  const chosen = candidates.filter((c) => selected.has(c.url));

  function toggle(url: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }

  return (
    <section
      className="t-reveal rounded-lg border border-border bg-card p-6"
      aria-label="Candidate sources to review"
    >
      <header className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-md border border-insufficient/30 bg-insufficient-subtle text-insufficient">
          <Search className="size-5" aria-hidden />
        </div>
        <div className="min-w-0">
          <h2 className="font-display text-lg leading-tight text-foreground">
            Not in your sources yet
          </h2>
          <p className="mt-1 text-sm text-foreground">
            This isn&apos;t in your approved materials — but these web sources may cover it. Pick the
            ones you trust. Approved pages join your corpus and the answer is re-verified against
            them (it still cites every claim, or abstains).
          </p>
        </div>
      </header>

      <ul className="mt-5 flex flex-col gap-2 border-t border-border pt-5">
        {candidates.map((c) => {
          const isSelected = selected.has(c.url);
          // Wikipedia/DuckDuckGo snippets come from the real page; a claude_web-only
          // snippet is model-written and may not reflect the page — flag it so the
          // approval decision isn't made on possibly-fabricated preview text.
          const aiSnippet = c.providers.length > 0 && c.providers.every((p) => p === "claude_web");
          return (
            <li key={c.url}>
              <button
                type="button"
                onClick={() => toggle(c.url)}
                aria-pressed={isSelected}
                disabled={confirm.isPending}
                className={cn(
                  "flex w-full items-start gap-3 rounded-md border p-3 text-left transition-colors",
                  isSelected ? "border-primary/50 bg-primary/5" : "border-border hover:bg-muted",
                )}
              >
                <span
                  className={cn(
                    "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded border",
                    isSelected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border",
                  )}
                  aria-hidden
                >
                  {isSelected && <Check className="size-3.5" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="truncate font-medium text-foreground">{c.title}</span>
                    {c.providers.map((p) => (
                      <span
                        key={p}
                        className="rounded-full border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground"
                      >
                        {PROVIDER_LABEL[p] ?? p}
                      </span>
                    ))}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                    <Globe className="size-3 shrink-0" aria-hidden />
                    <span className="truncate">{hostOf(c.url)}</span>
                  </span>
                  {c.snippet && (
                    <span className="mt-1 block text-sm text-muted-foreground">
                      {c.snippet}
                      {aiSnippet && (
                        <span className="ml-1 whitespace-nowrap text-[10px] uppercase tracking-wide text-insufficient">
                          AI-suggested · unverified
                        </span>
                      )}
                    </span>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-border pt-4">
        <Button
          onClick={() => confirm.mutate(chosen)}
          disabled={chosen.length === 0 || confirm.isPending}
        >
          {confirm.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Adding &amp; verifying…
            </>
          ) : (
            `Add ${chosen.length} source${chosen.length === 1 ? "" : "s"} & answer`
          )}
        </Button>
        <span className="text-xs text-muted-foreground">
          Each page is fetched and snapshotted; nothing is trusted until you approve it.
        </span>
      </div>
    </section>
  );
}
