/** SSE client for the answer pipeline. Uses fetch streaming (POST body), parses
 * event/data frames, and tolerates malformed frames. Cancellable via AbortSignal. */
import { API_BASE } from "@/lib/api/client";

export interface SseEvent {
  event: string;
  data: unknown;
}

export interface StreamAskBody {
  question: string;
  session_id?: string | null;
  subject_id?: string | null;
  approved_source_ids?: string[] | null;
  mode?: "grounded" | "premium";
}

export async function streamAnswer(
  body: StreamAskBody,
  onEvent: (e: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/answers/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Stream failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const parsed = parseFrame(frame);
      if (parsed) onEvent(parsed);
    }
  }
}

function parseFrame(frame: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null; // tolerate malformed data
  }
}
