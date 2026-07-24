import type { AnswerResponse } from "@/lib/api/schemas";
import { CLAIM_STATUS, TOP_LEVEL_STATUS } from "@/lib/verification";

/**
 * Serialize an answer into a self-contained, defensible plain-text artifact:
 * the verdict, the answer, a CITATIONS key that resolves every in-text `[n]`
 * marker to a source + passage, each claim with its exact cited quotations,
 * the source list, and the provenance IDs needed to reproduce it. This is what
 * an accountable user pastes into a brief or memo — the `[n]` markers in the
 * raw answer are useless on their own.
 */
export function buildCitedAnswer(answer: AnswerResponse): string {
  const status = TOP_LEVEL_STATUS[answer.status];
  const titleFor = (sourceId: string) =>
    answer.sources.find((s) => s.source_id === sourceId)?.title ?? sourceId;

  const lines: string[] = [];
  lines.push(answer.question.trim());
  lines.push("");
  lines.push(`STATUS: ${status.label}`);
  lines.push(status.description);
  lines.push("");
  lines.push("ANSWER");
  lines.push(answer.answer.trim() || "(no answer text)");

  if (answer.status === "CONTRADICTION" && answer.contradiction_detail) {
    lines.push("");
    lines.push("CONTRADICTION");
    lines.push(answer.contradiction_detail.trim());
  }

  // Resolve the in-text [n] markers: one entry per citation number, so a
  // pasted brief never carries a dangling [2].
  const citations = new Map<number, { sourceId: string; passageId: string; quotation?: string }>();
  for (const c of answer.claims) {
    for (const cit of c.citations) {
      if (!citations.has(cit.citation_number)) {
        const ev = c.evidence.find(
          (e) => e.source_id === cit.source_id && e.passage_id === cit.passage_id,
        );
        citations.set(cit.citation_number, {
          sourceId: cit.source_id,
          passageId: cit.passage_id,
          quotation: ev?.quotation,
        });
      }
    }
  }
  if (citations.size > 0) {
    lines.push("");
    lines.push("CITATIONS");
    [...citations.entries()]
      .sort((a, b) => a[0] - b[0])
      .forEach(([n, ref]) => {
        lines.push(`[${n}] ${titleFor(ref.sourceId)} (passage ${ref.passageId})`);
        if (ref.quotation) lines.push(`    "${ref.quotation.trim()}"`);
      });
  }

  if (answer.claims.length > 0) {
    lines.push("");
    lines.push("CLAIMS & EVIDENCE");
    answer.claims.forEach((c) => {
      const claimStatus = CLAIM_STATUS[c.status]?.label ?? c.status;
      const kind = c.material ? "material" : "supporting";
      lines.push(`- (${claimStatus}, ${kind}) ${c.text.trim()}`);
      if (c.evidence.length === 0) lines.push("    — no supporting quotation");
      c.evidence.forEach((e) => {
        lines.push(`    "${e.quotation.trim()}"`);
        lines.push(`    — ${titleFor(e.source_id)} (passage ${e.passage_id})`);
      });
    });
  }

  if (answer.sources.length > 0) {
    lines.push("");
    lines.push("SOURCES");
    answer.sources.forEach((s) => {
      const bits = [s.title];
      if (s.author) bits.push(s.author);
      if (s.publication_date) bits.push(s.publication_date);
      lines.push(`- ${bits.join(", ")}`);
    });
  }

  lines.push("");
  lines.push("PROVENANCE");
  lines.push(`Request ID: ${answer.request_id}`);
  lines.push(`Audit ID: ${answer.audit_id ?? "—"}`);
  lines.push(`Model: ${answer.pipeline.model_identifier ?? "deterministic"}`);
  lines.push(`Provider: ${answer.pipeline.provider}`);
  lines.push(`Generated: ${answer.created_at}`);
  lines.push("");
  lines.push(
    "Verified answers are supported only by the approved evidence available at generation time; they are not a claim of universal truth.",
  );

  return lines.join("\n");
}
