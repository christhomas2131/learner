import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api/client", () => ({ apiFetch: vi.fn() }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { apiFetch } from "@/lib/api/client";
import { DiscoveryPanel } from "@/features/ask/discovery-panel";
import type { AnswerResponse, CandidateOut } from "@/lib/api/schemas";

const CANDIDATES: CandidateOut[] = [
  { url: "https://a.org/x", title: "Alpha source", snippet: "about alpha",
    providers: ["wikipedia", "duckduckgo"] },
  { url: "https://b.org/y", title: "Beta source", snippet: "about beta",
    providers: ["claude_web"] },
];

const VERIFIED: AnswerResponse = {
  request_id: "r1", audit_id: "a1", session_id: "s1", status: "VERIFIED",
  question: "q", answer: "ans", claims: [], sources: [],
  pipeline: { attempts: 1, duration_ms: 1, completed_stages: [], provider: "none",
    model_identifier: null },
  candidates: [], discovery_id: null, created_at: "2026-01-01T00:00:00Z",
};

function renderPanel(candidates = CANDIDATES) {
  const onAnswer = vi.fn();
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <DiscoveryPanel question="q" sessionId="s1" discoveryId="disc-1"
        candidates={candidates} onAnswer={onAnswer} />
    </QueryClientProvider>,
  );
  return { onAnswer };
}

describe("DiscoveryPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists candidates with provider badges; all selected by default", () => {
    renderPanel();
    expect(screen.getByText("Alpha source")).toBeInTheDocument();
    expect(screen.getByText("Beta source")).toBeInTheDocument();
    expect(screen.getByText("Wikipedia")).toBeInTheDocument();
    expect(screen.getByText("DuckDuckGo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add 2 sources & answer/i })).toBeEnabled();
  });

  it("prunes a candidate and confirms only the selected ones", async () => {
    vi.mocked(apiFetch).mockResolvedValue(VERIFIED);
    const user = userEvent.setup();
    const { onAnswer } = renderPanel();

    await user.click(screen.getByRole("button", { name: /Beta source/i }));
    await user.click(screen.getByRole("button", { name: /add 1 source & answer/i }));

    expect(apiFetch).toHaveBeenCalledTimes(1);
    const [path, , opts] = vi.mocked(apiFetch).mock.calls[0] as [string, unknown, { body: {
      sources: { url: string; title: string }[] } }];
    expect(path).toBe("/api/v1/discovery/confirm");
    expect(opts.body.sources).toEqual([{ url: "https://a.org/x", title: "Alpha source" }]);
    expect(onAnswer).toHaveBeenCalledWith(VERIFIED);
  });
});
