/** Centralized typed API client. Validates every response with Zod; a schema
 * mismatch is an error. Normalizes backend + network errors into ApiError. */
import { z } from "zod";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const errorEnvelope = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string().nullable().optional(),
  }),
});

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  formData?: FormData;
  query?: Record<string, string | number | boolean | undefined>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(API_BASE + path);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  opts: RequestOptions = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? "GET",
      headers: opts.formData ? undefined : { "Content-Type": "application/json" },
      body: opts.formData ?? (opts.body ? JSON.stringify(opts.body) : undefined),
      signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(
      "Cannot reach the backend. Is it running?",
      "backend_unavailable",
      0,
    );
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const json = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const parsed = errorEnvelope.safeParse(json);
    if (parsed.success) {
      throw new ApiError(
        parsed.data.error.message,
        parsed.data.error.code,
        res.status,
        parsed.data.error.request_id ?? undefined,
      );
    }
    throw new ApiError(`Request failed (${res.status})`, "http_error", res.status);
  }

  const result = schema.safeParse(json);
  if (!result.success) {
    throw new ApiError(
      "The server returned data in an unexpected shape.",
      "schema_validation_error",
      res.status,
    );
  }
  return result.data;
}
