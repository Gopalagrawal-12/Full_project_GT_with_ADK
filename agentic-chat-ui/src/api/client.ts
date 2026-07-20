import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  IngestJob,
  IngestKind,
  TraceStep,
} from "../types/api";

/**
 * Base URL is read from VITE_API_BASE_URL at build time, falling back to
 * a same-origin relative path so the app also works if the frontend is
 * served behind a reverse proxy that forwards /api/*. It can be overridden
 * at runtime from the Settings panel (persisted in localStorage), which is
 * handy since no BASE_URL was pinned down in the spec.
 */
const ENV_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined;
const STORAGE_KEY_BASE_URL = "ingest-console.base_url";

export function getBaseUrl(): string {
  return (
    localStorage.getItem(STORAGE_KEY_BASE_URL) ?? ENV_BASE_URL ?? ""
  ).replace(/\/+$/, "");
}

export function setBaseUrl(url: string) {
  localStorage.setItem(STORAGE_KEY_BASE_URL, url.trim().replace(/\/+$/, ""));
}

class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getBaseUrl()}${path}`, init);
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.error ?? body?.detail ?? JSON.stringify(body);
    } catch {
      detail = await res.text().catch(() => "");
    }
    throw new ApiError(
      `${res.status} ${res.statusText}${detail ? ` — ${detail}` : ""}`,
      res.status
    );
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------
// Endpoint 1 & 2 — Chat
// ---------------------------------------------------------------------

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  return req<ChatResponse>(`/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/**
 * Streams `/api/v1/chat/stream` via fetch + a readable-stream reader
 * (works for both `text/event-stream` "data: {...}\n\n" framing and plain
 * newline-delimited JSON, since the exact framing wasn't pinned down in
 * the spec). Calls `onEvent` for every normalized event and resolves when
 * the stream ends.
 */
export async function streamChat(
  payload: ChatRequest,
  onEvent: (evt: ChatStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${getBaseUrl()}/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = "";
    try {
      detail = await res.text();
    } catch {
      /* noop */
    }
    throw new ApiError(
      `${res.status} ${res.statusText}${detail ? ` — ${detail}` : ""}`,
      res.status
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line; NDJSON by single newlines.
    // Split greedily on double-newline first, fall back to single-newline
    // chunks for any remainder so both framings are supported.
    let frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      handleFrame(frame, onEvent);
    }
  }
  if (buffer.trim()) {
    for (const line of buffer.split("\n")) handleFrame(line, onEvent);
  }
}

function handleFrame(frame: string, onEvent: (evt: ChatStreamEvent) => void) {
  const trimmed = frame.trim();
  if (!trimmed) return;

  // Strip SSE "event:"/"data:" prefixes if present, collecting the data lines.
  const dataLines = trimmed
    .split("\n")
    .filter((l) => l.startsWith("data:"))
    .map((l) => l.slice(5).trim());
  const raw = dataLines.length ? dataLines.join("\n") : trimmed;

  if (raw === "[DONE]") {
    onEvent({ type: "done" });
    return;
  }

  try {
    const parsed = JSON.parse(raw);
    onEvent(normalizeStreamEvent(parsed));
  } catch {
    // Not JSON — treat as a raw token chunk rather than dropping it.
    onEvent({ type: "token", content: raw });
  }
}

/** Normalizes a handful of plausible backend event shapes into ChatStreamEvent. */
function normalizeStreamEvent(parsed: any): ChatStreamEvent {
  const type = parsed.type ?? parsed.event ?? "";

  if (type === "trace_step" || parsed.node) {
    const step: TraceStep = {
      node: parsed.node ?? parsed.step?.node ?? "unknown",
      status: parsed.status ?? parsed.step?.status,
      state_delta: parsed.state_delta ?? parsed.step?.state_delta ?? {},
      started_at: parsed.started_at ?? null,
      finished_at: parsed.finished_at ?? null,
      duration_ms: parsed.duration_ms ?? null,
    };
    return { type: "trace_step", step };
  }
  if (type === "routing" || parsed.routed_to) {
    return { type: "routing", routedTo: parsed.routed_to ?? parsed.routedTo };
  }
  if (type === "token" || typeof parsed.delta === "string") {
    return { type: "token", content: parsed.content ?? parsed.delta ?? "" };
  }
  if (type === "message" && typeof parsed.content === "string") {
    return { type: "message", content: parsed.content };
  }
  if (type === "error" || parsed.error) {
    return { type: "error", message: parsed.error ?? parsed.message ?? "Unknown stream error" };
  }
  if (type === "done") {
    return { type: "done", sessionId: parsed.session_id };
  }
  // Fallback: assume it's a full message payload.
  if (typeof parsed.message === "string") {
    return { type: "message", content: parsed.message };
  }
  return { type: "token", content: JSON.stringify(parsed) };
}

// ---------------------------------------------------------------------
// Endpoint 3 & 4 — Ingestion (CSV rows / documents into vector store)
// ---------------------------------------------------------------------

export async function startIngest(
  kind: IngestKind,
  file: File,
  datasetLabel?: string
): Promise<IngestJob> {
  const path =
    kind === "csv" ? "/api/v1/ingest/" : "/api/v1/ingest/documents";
  const form = new FormData();
  form.append("file", file);
  if (datasetLabel?.trim()) form.append("dataset_label", datasetLabel.trim());

  return req<IngestJob>(path, { method: "POST", body: form });
}

export async function getIngestStatus(
  kind: IngestKind,
  jobId: string
): Promise<IngestJob> {
  const path =
    kind === "csv"
      ? "/api/v1/ingest/status"
      : "/api/v1/ingest/documents/status";
  const qs = new URLSearchParams({ job_id: jobId }).toString();
  return req<IngestJob>(`${path}?${qs}`, { method: "GET" });
}

export { ApiError };
