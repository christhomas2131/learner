/** Zod schemas mirroring the backend contracts. Schema-validation failures are
 * treated as errors — the backend is authoritative, the frontend never guesses. */
import { z } from "zod";

export const topLevelStatus = z.enum([
  "VERIFIED",
  "INSUFFICIENT_EVIDENCE",
  "CONTRADICTION",
  "ERROR",
]);
export type TopLevelStatus = z.infer<typeof topLevelStatus>;

export const claimStatus = z.enum(["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]);
export type ClaimStatus = z.infer<typeof claimStatus>;

export const sourceType = z.enum([
  "CURATED_MARKDOWN",
  "UPLOADED_TEXT",
  "UPLOADED_PDF",
  "UPLOADED_DOCX",
  "APPROVED_WEBSITE",
  "STRUCTURED_RECORD",
  "ANSWER_KEY",
]);
export const sourceState = z.enum([
  "UPLOADED",
  "PROCESSING",
  "PENDING_APPROVAL",
  "APPROVED",
  "REJECTED",
  "FAILED",
  "ARCHIVED",
]);
export const queueStatus = z.enum(["PENDING", "PROCESSING", "DONE", "FAILED"]);

export const citationOut = z.object({
  citation_number: z.number(),
  source_id: z.string(),
  passage_id: z.string(),
});

export const evidenceOut = z.object({
  source_id: z.string(),
  passage_id: z.string(),
  quotation: z.string(),
  retrieval_score: z.number(),
});

export const claimOut = z.object({
  claim_id: z.string(),
  text: z.string(),
  material: z.boolean(),
  status: claimStatus,
  citations: z.array(citationOut),
  evidence: z.array(evidenceOut),
  verifier_explanation: z.string(),
});
export type ClaimOut = z.infer<typeof claimOut>;

export const sourceRef = z.object({
  source_id: z.string(),
  title: z.string(),
  source_type: z.string(),
  approved: z.boolean(),
  author: z.string().nullable().optional(),
  organization: z.string().nullable().optional(),
  publication_date: z.string().nullable().optional(),
  url: z.string().nullable().optional(),
});

export const pipelineInfo = z.object({
  attempts: z.number(),
  duration_ms: z.number(),
  completed_stages: z.array(z.string()),
  provider: z.string(),
  model_identifier: z.string().nullable().optional(),
});

export const answerResponse = z.object({
  request_id: z.string(),
  audit_id: z.string().nullable(),
  session_id: z.string().nullable(),
  status: topLevelStatus,
  question: z.string(),
  answer: z.string(),
  claims: z.array(claimOut),
  sources: z.array(sourceRef),
  pipeline: pipelineInfo,
  contradiction_detail: z.string().nullable().optional(),
  created_at: z.string(),
});
export type AnswerResponse = z.infer<typeof answerResponse>;

export const enqueueResponse = z.object({
  queue_id: z.string(),
  session_id: z.string(),
  request_id: z.string(),
  status: queueStatus,
});
export type EnqueueResponse = z.infer<typeof enqueueResponse>;

export const sessionOut = z.object({
  id: z.string(),
  title: z.string(),
  subject_id: z.string().nullable(),
  saved: z.boolean(),
  is_demo: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type SessionOut = z.infer<typeof sessionOut>;

export const messageOut = z.object({
  id: z.string(),
  role: z.string(),
  content: z.string(),
  created_at: z.string(),
});

export const answerSummary = z.object({
  id: z.string(),
  question: z.string(),
  status: topLevelStatus,
  answer_text: z.string(),
  created_at: z.string(),
});

export const sessionDetail = sessionOut.extend({
  messages: z.array(messageOut),
  answers: z.array(answerSummary),
});
export type SessionDetail = z.infer<typeof sessionDetail>;

export const subjectOut = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  source_count: z.number(),
});
export type SubjectOut = z.infer<typeof subjectOut>;

export const sourceOut = z.object({
  id: z.string(),
  title: z.string(),
  source_type: sourceType,
  state: sourceState,
  is_demo: z.boolean(),
  subject_id: z.string().nullable(),
  author: z.string().nullable(),
  organization: z.string().nullable(),
  publication_date: z.string().nullable(),
  url: z.string().nullable(),
  content_hash: z.string(),
  original_filename: z.string().nullable(),
  byte_size: z.number(),
  passage_count: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type SourceOut = z.infer<typeof sourceOut>;

export const passageOut = z.object({
  id: z.string(),
  chunk_index: z.number(),
  text: z.string(),
});

export const queueItemOut = z.object({
  id: z.string(),
  session_id: z.string(),
  request_id: z.string(),
  question: z.string(),
  status: queueStatus,
  answer_id: z.string().nullable(),
  error: z.string().nullable(),
  created_at: z.string(),
});
export type QueueItemOut = z.infer<typeof queueItemOut>;

export const analytics = z.object({
  questions_asked: z.number(),
  verified_rate: z.number(),
  abstention_rate: z.number(),
  contradiction_rate: z.number(),
  error_rate: z.number(),
  average_duration_ms: z.number(),
  average_claim_count: z.number(),
  status_breakdown: z.record(z.string(), z.number()),
  sessions_over_time: z.array(z.object({ date: z.string(), count: z.number() })),
  most_studied_subjects: z.array(z.object({ subject: z.string(), count: z.number() })),
  source_usage: z.array(z.object({ type: z.string(), count: z.number() })),
  recent_activity: z.array(
    z.object({ question: z.string(), status: z.string(), created_at: z.string() }),
  ),
});
export type Analytics = z.infer<typeof analytics>;

export const workerStatus = z.object({
  online: z.boolean(),
  last_seen: z.string().nullable(),
});
export type WorkerStatus = z.infer<typeof workerStatus>;

export function page<T extends z.ZodTypeAny>(item: T) {
  return z.object({
    items: z.array(item),
    total: z.number(),
    limit: z.number(),
    offset: z.number(),
  });
}
