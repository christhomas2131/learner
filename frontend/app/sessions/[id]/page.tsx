"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { Bookmark, BookmarkCheck, Download } from "lucide-react";
import { useSession, useUpdateSession } from "@/lib/api/hooks";
import { API_BASE } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/misc";
import { StatusBadge } from "@/components/ui/status-badge";
import { AskWorkspace } from "@/features/ask/ask-workspace";
import { formatRelative } from "@/lib/utils";

export default function SessionPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data, isLoading, isError } = useSession(id);
  const update = useUpdateSession();

  if (isError)
    return (
      <div className="p-8 text-sm text-error">Session not found or backend unavailable.</div>
    );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-border p-4">
        <div className="min-w-0">
          {isLoading ? (
            <Skeleton className="h-6 w-48" />
          ) : (
            <>
              <h1 className="truncate text-lg font-semibold">{data?.title}</h1>
              <p className="text-xs text-muted-foreground">
                {data && formatRelative(data.updated_at)}
              </p>
            </>
          )}
        </div>
        {data && (
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" asChild>
              <a href={`${API_BASE}/api/v1/sessions/${id}/export.docx`} download>
                <Download className="size-4" /> Export
              </a>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => update.mutate({ id, saved: !data.saved })}
            >
              {data.saved ? <BookmarkCheck className="size-4" /> : <Bookmark className="size-4" />}
              {data.saved ? "Saved" : "Save"}
            </Button>
          </div>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto scroll-slim">
        {data && data.answers.length > 0 && (
          <div className="mx-auto w-full max-w-3xl space-y-4 p-5 md:p-8">
            <p className="text-xs font-medium text-muted-foreground">History</p>
            {data.answers.map((a) => (
              <div key={a.id} className="rounded-lg border border-border bg-card p-4">
                <p className="mb-2 text-sm font-medium">{a.question}</p>
                <div className="mb-2">
                  <StatusBadge status={a.status} size="sm" />
                </div>
                <p className="text-sm text-muted-foreground">{a.answer_text || "—"}</p>
              </div>
            ))}
          </div>
        )}
        <AskWorkspace sessionId={id} />
      </div>
    </div>
  );
}
