import type { ChatSseEvent, IngestionKind, IngestionStatusResponseApi } from '@/types';

// Centralize the backend origin so it's a one-line change for deployment.
export const API_BASE = import.meta.env.VITE_ADK_API_BASE ?? 'http://localhost:8000';

// The routes in chat_routes.py / ingest_routes.py / vector_ingest_routes.py are
// shown unprefixed (e.g. "/chat/stream"). If your FastAPI app mounts these
// routers under a prefix (e.g. app.include_router(router, prefix="/api/v1")),
// set VITE_ADK_API_PREFIX accordingly — everything else stays the same.
const API_PREFIX = import.meta.env.VITE_ADK_API_PREFIX ?? '';

const ENDPOINTS = {
  chatStream: `${API_PREFIX}/api/v1/chat/stream`,
  ingestStructured: `${API_PREFIX}/api/v1/ingest`,
  ingestStructuredStatus: `${API_PREFIX}/api/v1/ingest/status`,
  ingestDocuments: `${API_PREFIX}/api/v1/ingest/documents`,
  ingestDocumentsStatus: `${API_PREFIX}/api/v1/ingest/documents/status`,
};

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Parses a fetch ReadableStream as Server-Sent Events. Frames look like:
 *   event: agent_step\ndata: {"agent": "...", ...}\n\n
 * Frames are separated by a blank line and may arrive split across chunk
 * boundaries, so we buffer until we see a full "\n\n"-terminated block.
 */
async function* parseSseStream(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatSseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() || ''; // keep the last (possibly incomplete) frame

      for (const frame of frames) {
        const event = parseSseFrame(frame);
        if (event) yield event;
      }
    }
    if (buffer.trim()) {
      const event = parseSseFrame(buffer);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}

function parseSseFrame(frame: string): ChatSseEvent | null {
  let eventType = 'message';
  const dataLines: string[] = [];

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) eventType = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;

  try {
    const payload = JSON.parse(dataLines.join('\n'));
    return { ...payload, type: eventType } as ChatSseEvent;
  } catch (e) {
    console.error('Failed to parse SSE frame:', frame, e);
    return null;
  }
}

/**
 * Opens POST /chat/stream and hands each parsed SSE frame to `onEvent` as an
 * agent_step, final, or error event.
 */
export async function streamChat(
  message: string,
  userId: string,
  sessionId: string | null,
  onEvent: (event: ChatSseEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE}${ENDPOINTS.chatStream}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, user_id: userId, session_id: sessionId }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new ApiError(`Chat stream failed: ${response.statusText}`, response.status);
  }

  for await (const event of parseSseStream(response.body)) {
    onEvent(event);
  }
}

/**
 * Kicks off ingestion for either upload zone. `dataset_label` is a query
 * param, not a form field — the FastAPI handlers only declare `file` as
 * File(...), so plain params alongside it are bound from the querystring.
 * Returns the full IngestionStatusResponse (job already has an id + initial
 * status, so the caller doesn't need to wait for the first poll to render).
 */
export async function uploadIngestionFile(
  kind: IngestionKind,
  file: File,
  datasetLabel?: string
): Promise<IngestionStatusResponseApi> {
  const endpoint = kind === 'structured' ? ENDPOINTS.ingestStructured : ENDPOINTS.ingestDocuments;
  const url = new URL(`${API_BASE}${endpoint}`);
  if (datasetLabel) url.searchParams.set('dataset_label', datasetLabel);

  const form = new FormData();
  form.append('file', file);

  const response = await fetch(url.toString(), { method: 'POST', body: form });
  if (!response.ok) {
    throw new ApiError(`Upload failed: ${response.statusText}`, response.status);
  }
  return response.json();
}

/** job_id is a querystring param on both status routes, not a path segment. */
export async function fetchIngestionStatus(
  kind: IngestionKind,
  jobId: string
): Promise<IngestionStatusResponseApi> {
  const endpoint = kind === 'structured' ? ENDPOINTS.ingestStructuredStatus : ENDPOINTS.ingestDocumentsStatus;
  const url = new URL(`${API_BASE}${endpoint}`);
  url.searchParams.set('job_id', jobId);

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new ApiError(`Status check failed: ${response.statusText}`, response.status);
  }
  return response.json();
}
