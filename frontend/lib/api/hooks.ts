/** TanStack Query hooks over the typed client. */
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import {
  analytics,
  answerResponse,
  enqueueResponse,
  page,
  passageOut,
  queueItemOut,
  sessionDetail,
  sessionOut,
  sourceOut,
  subjectOut,
  workerStatus,
  type Analytics,
  type QueueItemOut,
  type SessionDetail,
  type SourceOut,
} from "@/lib/api/schemas";
import { z } from "zod";

export const keys = {
  sessions: (q?: object) => ["sessions", q ?? {}] as const,
  session: (id: string) => ["session", id] as const,
  sources: (q?: object) => ["sources", q ?? {}] as const,
  source: (id: string) => ["source", id] as const,
  passages: (id: string) => ["passages", id] as const,
  subjects: ["subjects"] as const,
  analytics: ["analytics"] as const,
  queueItem: (id: string) => ["queue", id] as const,
};

export function useSessions(params: { saved?: boolean; search?: string } = {}) {
  return useQuery({
    queryKey: keys.sessions(params),
    queryFn: () =>
      apiFetch("/api/v1/sessions", page(sessionOut), {
        query: { saved: params.saved, search: params.search, limit: 100 },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useSession(id: string | null) {
  return useQuery({
    queryKey: keys.session(id ?? ""),
    queryFn: () => apiFetch(`/api/v1/sessions/${id}`, sessionDetail),
    enabled: !!id,
  });
}

export function useUpdateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; title?: string; saved?: boolean }) =>
      apiFetch(`/api/v1/sessions/${id}`, sessionOut, { method: "PATCH", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/sessions/${id}`, z.undefined(), { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function useSources(params: { state?: string; search?: string } = {}) {
  return useQuery({
    queryKey: keys.sources(params),
    queryFn: () =>
      apiFetch("/api/v1/sources", page(sourceOut), {
        query: { state: params.state, search: params.search, limit: 100 },
      }),
    placeholderData: keepPreviousData,
  });
}

export function usePassages(id: string | null) {
  return useQuery({
    queryKey: keys.passages(id ?? ""),
    queryFn: () => apiFetch(`/api/v1/sources/${id}/passages`, z.array(passageOut)),
    enabled: !!id,
  });
}

export function useUploadSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { file: File; title?: string; subject_id?: string }) => {
      const fd = new FormData();
      fd.append("file", input.file);
      if (input.title) fd.append("title", input.title);
      if (input.subject_id) fd.append("subject_id", input.subject_id);
      return apiFetch("/api/v1/sources/upload", sourceOut, { method: "POST", formData: fd });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
}

export function useAddWebsite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { url: string; subject_id?: string }) =>
      apiFetch("/api/v1/sources/website", sourceOut, { method: "POST", body: input }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
}

export function useSourceAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" | "reindex" }) =>
      apiFetch(`/api/v1/sources/${id}/${action}`, sourceOut, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
}

export function useDeleteSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/sources/${id}`, z.undefined(), { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
}

export function useSubjects() {
  return useQuery({
    queryKey: keys.subjects,
    queryFn: () => apiFetch("/api/v1/subjects", z.array(subjectOut)),
  });
}

export function useCreateSubject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      apiFetch("/api/v1/subjects", subjectOut, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.subjects }),
  });
}

export function useAnalytics() {
  return useQuery<Analytics>({
    queryKey: keys.analytics,
    queryFn: () => apiFetch("/api/v1/analytics", analytics),
  });
}

export function useWorkerStatus() {
  return useQuery({
    queryKey: ["worker-status"],
    queryFn: () => apiFetch("/api/v1/worker/status", workerStatus),
    refetchInterval: 10_000,
    retry: false,
  });
}

export function useAnswer(answerId: string | null) {
  return useQuery({
    queryKey: ["answer", answerId ?? ""],
    queryFn: () => apiFetch(`/api/v1/answers/${answerId}`, answerResponse),
    enabled: !!answerId,
  });
}

/** Poll a premium queue item until it reaches a terminal state. */
export function useQueueItem(id: string | null, enabled: boolean) {
  return useQuery<QueueItemOut>({
    queryKey: keys.queueItem(id ?? ""),
    queryFn: () => apiFetch(`/api/v1/queue/${id}`, queueItemOut),
    enabled: !!id && enabled,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "DONE" || s === "FAILED" ? false : 1500;
    },
  });
}

export type { SessionDetail, SourceOut };
export { answerResponse, enqueueResponse };
