import { describe, expect, it } from "vitest";
import { buildCitedAnswer } from "@/lib/export-answer";
import type { AnswerResponse } from "@/lib/api/schemas";

const base: AnswerResponse = {
  request_id: "req_123",
  audit_id: "aud_456",
  session_id: null,
  status: "VERIFIED",
  question: "What is photosynthesis?",
  answer: "Photosynthesis converts light into chemical energy [1].",
  claims: [
    {
      claim_id: "c1",
      text: "Photosynthesis converts light into chemical energy.",
      material: true,
      status: "SUPPORTED",
      citations: [{ citation_number: 1, source_id: "s1", passage_id: "p1" }],
      evidence: [
        {
          source_id: "s1",
          passage_id: "p1",
          quotation: "light energy is converted into chemical energy",
          retrieval_score: 0.91,
        },
      ],
      verifier_explanation: "",
    },
  ],
  sources: [
    {
      source_id: "s1",
      title: "Biology 101",
      source_type: "CURATED_MARKDOWN",
      approved: true,
      author: "Jane Doe",
      publication_date: "2020",
    },
  ],
  pipeline: {
    attempts: 1,
    duration_ms: 12,
    completed_stages: ["RELEASE_GATE"],
    provider: "deterministic",
    model_identifier: null,
  },
  contradiction_detail: null,
  created_at: "2026-07-24T00:00:00Z",
};

describe("buildCitedAnswer", () => {
  it("includes the question, verdict, answer, cited quotation, source, and provenance", () => {
    const out = buildCitedAnswer(base);
    expect(out).toContain("What is photosynthesis?");
    expect(out).toContain("STATUS: Verified");
    expect(out).toContain("Photosynthesis converts light into chemical energy [1].");
    expect(out).toContain('"light energy is converted into chemical energy"');
    expect(out).toContain("Biology 101 (passage p1)");
    // in-text [1] must resolve to a citation entry with its quoted sentence, not dangle
    expect(out).toContain("CITATIONS");
    expect(out).toMatch(
      /\[1\] Biology 101 \(passage p1\)\n\s*"light energy is converted into chemical energy"/,
    );
    expect(out).toContain("Request ID: req_123");
    expect(out).toContain("Audit ID: aud_456");
    // model_identifier null on a deterministic run must render as "deterministic"
    expect(out).toContain("Model: deterministic");
  });

  it("labels abstention and shows an em dash for a missing audit id", () => {
    const out = buildCitedAnswer({
      ...base,
      status: "INSUFFICIENT_EVIDENCE",
      audit_id: null,
    });
    expect(out).toContain("STATUS: Insufficient Evidence");
    expect(out).toContain("Audit ID: —");
  });

  it("includes the contradiction detail only for a contradiction", () => {
    const out = buildCitedAnswer({
      ...base,
      status: "CONTRADICTION",
      contradiction_detail: "Source A says X; source B says not-X.",
    });
    expect(out).toContain("CONTRADICTION");
    expect(out).toContain("Source A says X; source B says not-X.");
  });
});
