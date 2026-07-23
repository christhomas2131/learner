"use client";

import * as React from "react";
import { CheckCircle2, FileText, Trash2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";
import {
  useDeleteSource,
  usePassages,
  useSourceAction,
  useSources,
  useUploadSource,
} from "@/lib/api/hooks";
import type { SourceOut } from "@/lib/api/schemas";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

const FILTERS = ["ALL", "PENDING_APPROVAL", "APPROVED", "REJECTED"] as const;

export default function LibraryPage() {
  const [filter, setFilter] = React.useState<(typeof FILTERS)[number]>("ALL");
  const { data, isLoading, isError } = useSources({
    state: filter === "ALL" ? undefined : filter,
  });
  const upload = useUploadSource();
  const [inspect, setInspect] = React.useState<SourceOut | null>(null);
  const [dragging, setDragging] = React.useState(false);

  const pending = data?.items.filter((s) => s.state === "PENDING_APPROVAL") ?? [];

  function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      upload.mutate(
        { file },
        {
          onSuccess: () => toast.success(`Uploaded ${file.name} — pending approval`),
          onError: (e) =>
            toast.error(e instanceof ApiError ? e.message : `Failed to upload ${file.name}`),
        },
      );
    }
  }

  return (
    <div className="mx-auto h-full w-full max-w-5xl overflow-y-auto scroll-slim p-5 md:p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight">Knowledge library</h1>
        <p className="measure mt-2 text-sm text-muted-foreground">
          Uploaded material is never trusted until you approve it. Only approved sources are used as
          evidence.
        </p>
      </div>

      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={cn(
          "mb-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border p-8 text-center transition-colors hover:bg-muted/50",
          dragging && "border-primary bg-accent/40",
        )}
      >
        <Upload className="size-6 text-muted-foreground" />
        <span className="text-sm font-medium">
          {upload.isPending ? "Uploading…" : "Drop a file or click to upload"}
        </span>
        <span className="text-xs text-muted-foreground">Markdown, TXT, PDF, or DOCX</span>
        <input
          type="file"
          className="hidden"
          accept=".md,.markdown,.txt,.pdf,.docx"
          multiple
          onChange={(e) => handleFiles(e.target.files)}
        />
      </label>

      {pending.length > 0 && (
        <div className="mb-6 rounded-lg border border-insufficient/30 bg-insufficient-subtle p-4">
          <p className="text-sm font-medium text-insufficient">
            {pending.length} source{pending.length === 1 ? "" : "s"} awaiting approval
          </p>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              filter === f ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted",
            )}
          >
            {f.replace("_", " ").toLowerCase()}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}
      {isError && (
        <p className="rounded-md border border-error/40 bg-error-subtle p-4 text-sm text-error">
          Could not load sources. Is the backend running?
        </p>
      )}
      {data && data.items.length === 0 && (
        <p className="py-12 text-center text-sm text-muted-foreground">
          No sources yet. Upload one above to get started.
        </p>
      )}

      <div className="space-y-3">
        {data?.items.map((s) => (
          <SourceCard key={s.id} source={s} onInspect={() => setInspect(s)} />
        ))}
      </div>

      <Dialog open={!!inspect} onOpenChange={(o) => !o && setInspect(null)}>
        <DialogContent className="max-w-2xl">
          {inspect && (
            <>
              <DialogHeader>
                <DialogTitle>{inspect.title}</DialogTitle>
                <DialogDescription>
                  {inspect.passage_count} passage(s) · {inspect.source_type}
                </DialogDescription>
              </DialogHeader>
              <PassageList sourceId={inspect.id} />
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SourceCard({ source, onInspect }: { source: SourceOut; onInspect: () => void }) {
  const action = useSourceAction();
  const del = useDeleteSource();
  const isPending = source.state === "PENDING_APPROVAL";

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <button onClick={onInspect} className="flex min-w-0 items-start gap-3 text-left">
          <FileText className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <p className="truncate font-medium">{source.title}</p>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
              <Badge variant="outline">{source.source_type}</Badge>
              <StateBadge state={source.state} />
              <span>{source.passage_count} passages</span>
              {source.is_demo && <Badge>demo</Badge>}
            </div>
          </div>
        </button>
        <div className="flex shrink-0 items-center gap-1">
          {isPending && (
            <>
              <Button size="sm" onClick={() => action.mutate({ id: source.id, action: "approve" })}>
                <CheckCircle2 className="size-4" /> Approve
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => action.mutate({ id: source.id, action: "reject" })}
              >
                <X className="size-4" /> Reject
              </Button>
            </>
          )}
          <Button
            size="icon"
            variant="ghost"
            aria-label="Delete source"
            onClick={() => del.mutate(source.id)}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

function StateBadge({ state }: { state: string }) {
  const tone =
    state === "APPROVED"
      ? "text-verified"
      : state === "PENDING_APPROVAL"
        ? "text-insufficient"
        : state === "REJECTED" || state === "FAILED"
          ? "text-contradiction"
          : "text-muted-foreground";
  return <span className={cn("font-medium", tone)}>{state.replace("_", " ").toLowerCase()}</span>;
}

function PassageList({ sourceId }: { sourceId: string }) {
  const { data, isLoading } = usePassages(sourceId);
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  return (
    <div className="max-h-[60vh] space-y-2 overflow-y-auto scroll-slim">
      {data?.map((p) => (
        <div key={p.id} className="rounded-md border border-border p-3 text-sm">
          <span className="text-xs text-muted-foreground">#{p.chunk_index}</span>
          <p className="mt-1 whitespace-pre-wrap">{p.text}</p>
        </div>
      ))}
    </div>
  );
}
