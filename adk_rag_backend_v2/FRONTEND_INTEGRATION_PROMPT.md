# Frontend Integration Prompt

Copy everything below into another AI coding assistant (e.g. a frontend-focused
LLM/IDE agent) to generate a working frontend against this backend.

---

## PROMPT START

You are building a frontend for a multi-agent AI analytics backend. The
backend is already built and running — your job is ONLY the frontend. Do not
invent endpoints or fields beyond what's specified below; the shapes below
are exact and verified against the running API.

### What this product does

The backend answers natural-language questions over two kinds of ingested
data — structured tables (CSV) and unstructured documents (Markdown/PDF/etc.)
— by routing each question through a 10-agent pipeline that decides which
data surface to use, retrieves the answer, and reasons over it. Build a UI
with three parts:

1. **A chat interface** — the primary surface. User types a question, gets a
   natural-language answer, optionally sees the SQL that was run or the
   documents that were cited.
2. **A live "agent trace" panel** (like Google ADK's web UI / like a build
   log) — while a question is being answered, show which agent is currently
   running, in sequence, with what it produced. This is the single most
   important UX requirement: the user should be able to watch the pipeline
   think, not just wait for a spinner.
3. **Two data ingestion panels** — one to upload a CSV into the tabular data
   lake, one to upload a document (.md/.txt, or richer formats if the backend
   has the optional docling extra installed) into the vector store. Both show
   a progress bar driven by polling.

### Base URL

All endpoints are under `{BASE_URL}/api/v1` (default `http://localhost:8000/api/v1`
in local dev — make this configurable, e.g. via an env var or a settings
field in the UI). `/health` (no `/api/v1` prefix) is a liveness check.

### Endpoint 1 — Ask a question (non-streaming)

```
POST {BASE_URL}/api/v1/chat
Content-Type: application/json

Request body:
{
  "message": "string, required — the user's question",
  "session_id": "string, optional — omit on first turn, then reuse the one returned",
  "user_id": "string, optional, default 'anonymous' — use a stable per-browser id"
}

Response body (200):
{
  "session_id": "string",
  "answer": "string — the natural-language answer, render as markdown",
  "query_path": "SQL" | "VECTOR" | null,
  "sql_executed": "string | null — populated only when query_path === 'SQL'",
  "row_count": "number | null",
  "elapsed_ms": "number"
}

Error (502): { "detail": "string" } — pipeline ran but produced no answer.
```

Use this for a simple "ask and wait" UX. Use Endpoint 2 for the live trace panel.

### Endpoint 2 — Ask a question, streamed with live agent trace (USE THIS for the trace panel)

```
POST {BASE_URL}/api/v1/chat/stream
Content-Type: application/json
Body: identical to Endpoint 1.

Response: text/event-stream (Server-Sent Events). Consume with the browser's
native EventSource is NOT viable here because this is a POST with a JSON
body — use `fetch()` with a ReadableStream reader, or a small SSE-over-POST
helper library, and parse frames of the form:

event: agent_step
data: {"agent": "query_understanding", "route": null,
       "state_delta": {"parsed_intent": "{...json string...}"},
       "partial_text": null, "timestamp": 1737300000.123}

event: agent_step
data: {"agent": "route_by_classification", "route": "SQL",
       "state_delta": {}, "partial_text": null, "timestamp": 1737300000.456}

... one agent_step frame per node the pipeline actually runs ...

event: final
data: {"session_id": "string", "answer": "string", "query_path": "SQL"|"VECTOR"|null,
       "sql_executed": "string|null", "row_count": "number|null", "elapsed_ms": "number"}

event: error   (only on failure, terminates the stream)
data: {"message": "string"}
```

**How to render the trace panel:**
- Maintain an ordered list of "steps", one per `agent_step` frame received, in
  arrival order.
- The possible `agent` values, in the order they CAN appear (not every run
  hits every node — it's one branch or the other after `route_by_classification`):
  `load_schema_context` → `query_understanding` → `query_classification` →
  `route_by_classification` → then EITHER
  (`time_lag` → `query_generation` → `query_review` → `query_execution` → `query_visualization`)
  OR (`vector_retrieval` → `vector_synthesis`) → `check_fallback` → optionally `external_support`.
- Show each step as a row/card with: an icon or label for the agent name
  (humanize it, e.g. `query_understanding` → "Understanding your question"),
  a "running" state when its frame first arrives and a "done" state as soon
  as the NEXT frame arrives (there's no explicit "started" event — a step is
  "running" until the next one shows up, and the last one is "done" when the
  `final` frame arrives).
  If `route` is non-null, show it as a small badge (e.g. "→ SQL" or "→ VECTOR"
  or "→ needs support") — this is the pipeline's routing decision, worth
  calling out visually since it's a branch point.
- If `state_delta` is non-empty, show it in an expandable "details" section
  per step (pretty-printed JSON) — this is literally what that agent
  produced/wrote, i.e. its "parameters" in the ADK-web-ui sense. Values are
  often JSON-encoded strings (e.g. `parsed_intent` is a JSON string, not an
  object) — parse them before pretty-printing if you want nested formatting,
  but fall back to showing the raw string if parsing fails.
- On the `final` frame, stop the trace, render `answer` as the chat message
  (markdown), and if `sql_executed` is present, offer a "show SQL" toggle
  under the message.
- On an `error` frame, show the trace up to that point plus a clear error
  state — don't silently discard the partial trace.

### Endpoint 3 — Ingest a CSV into the tabular data lake

```
POST {BASE_URL}/api/v1/ingest
Content-Type: multipart/form-data
Fields: file (the CSV), dataset_label (optional string query param or form field)

Response (200) — an ingestion job, poll its job_id:
{
  "job_id": "string",
  "status": "idle" | "processing" | "completed" | "failed",
  "current_step": "string, e.g. 'parsing_file' | 'validating_rows' | 'inserting_data_rows' | 'done'",
  "progress_pct": "number 0-100",
  "file_name": "string | null",
  "rows_ingested": "number",
  "error": "string | null",
  "started_at": "ISO datetime | null",
  "finished_at": "ISO datetime | null"
}
```

Poll `GET {BASE_URL}/api/v1/ingest/status?job_id={job_id}` (same response
shape) every ~1s until `status` is `completed` or `failed`. Render
`progress_pct` as a progress bar and `current_step` as a status label.

### Endpoint 4 — Ingest a document into the vector store

```
POST {BASE_URL}/api/v1/ingest/documents
Content-Type: multipart/form-data
Fields: file (.md/.txt always supported; .pdf/.docx/.pptx/.xlsx/.html if the
        backend has the optional docling extra installed), dataset_label (optional)

Response + polling: IDENTICAL shape to Endpoint 3, but poll
GET {BASE_URL}/api/v1/ingest/documents/status?job_id={job_id} instead.
current_step values differ slightly: "parsing_file" | "chunking" |
"embedding" | "storing" | "done". `rows_ingested` here means chunks created.
```

Build these two upload panels with the same component (they're structurally
identical), just pointed at different endpoints and with different accepted
file types / labels ("Structured data (CSV)" vs "Documents").

### UX requirements

- Persist `session_id` per chat conversation (e.g. in component state or
  localStorage) and pass it on every subsequent `/chat` or `/chat/stream`
  call in that conversation so the backend keeps context.
- Generate and persist a stable `user_id` per browser (random UUID in
  localStorage is fine) and send it on every request.
- Handle the "no data ingested yet" case gracefully — the backend will still
  answer, typically routing to `external_support` with a message explaining
  nothing's been ingested. Don't treat this as a frontend error.
- Keep the trace panel collapsible/dismissible — it's a power-user/debug
  feature, the chat answer is the primary deliverable, but it should be
  genuinely useful for understanding WHY an answer came out a certain way
  (e.g. seeing `query_classification`'s `state_delta` shows the reasoning
  behind the SQL vs VECTOR decision).
- Use whatever framework/component library you're set up for — no framework
  is mandated by the backend. Keep API calls in a small typed client module
  (e.g. `api/client.ts`) rather than scattered `fetch` calls, since there are
  only 6 endpoints total.

### What NOT to build

- Don't build any auth UI — the backend has none yet (`user_id` is
  self-reported).
- Don't try to call individual agents directly — there is no such endpoint;
  the only way to invoke the pipeline is `/chat` or `/chat/stream`, which run
  the whole graph.
- Don't assume a fixed set of "table names" or "document categories" in the
  UI — this backend is intentionally domain-agnostic; whatever gets ingested
  is what becomes queryable. Keep upload panels generic (no hardcoded
  business-domain labels beyond the optional free-text `dataset_label`).

## PROMPT END
