"use client";

import * as React from "react";
import { usePassages } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea, Skeleton } from "@/components/ui/misc";

const norm = (s: string) => s.replace(/\s+/g, " ").trim().toLowerCase();

/** Full-source reader that highlights the cited quotation in context. */
export function SourceViewer({
  sourceId,
  sourceTitle,
  quotation,
  open,
  onOpenChange,
}: {
  sourceId: string | null;
  sourceTitle?: string;
  quotation?: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const { data: passages, isLoading } = usePassages(open ? sourceId : null);
  const targetRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (passages && targetRef.current) {
      const id = window.setTimeout(
        () => targetRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }),
        120,
      );
      return () => window.clearTimeout(id);
    }
  }, [passages, quotation]);

  const nq = quotation ? norm(quotation) : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{sourceTitle ?? "Source"}</DialogTitle>
          <DialogDescription>The cited passage is highlighted in context.</DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <ScrollArea className="max-h-[60vh]">
            <div className="space-y-3 pr-2">
              {passages?.map((p) => {
                const isTarget = !!nq && norm(p.text).includes(nq);
                const exact = quotation && p.text.includes(quotation);
                return (
                  <div
                    key={p.id}
                    ref={isTarget ? targetRef : undefined}
                    className={cn(
                      "rounded-md border p-3 text-sm leading-relaxed whitespace-pre-wrap",
                      isTarget ? "border-primary/40 bg-accent/40" : "border-border",
                    )}
                  >
                    {isTarget && exact ? (
                      <Highlighted text={p.text} quote={quotation!} />
                    ) : (
                      p.text
                    )}
                  </div>
                );
              })}
              {passages && passages.length === 0 && (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  No passages for this source.
                </p>
              )}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Highlighted({ text, quote }: { text: string; quote: string }) {
  const idx = text.indexOf(quote);
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded bg-verified-subtle px-0.5 text-verified">{quote}</mark>
      {text.slice(idx + quote.length)}
    </>
  );
}
