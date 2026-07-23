# Agent Console

A split-pane frontend for a Google ADK multi-agent pipeline: chat on the left,
a live streaming trace of agent execution on the right.

## Run it

```bash
npm install
npm run dev
```

By default the app talks to `http://localhost:8000`. Override with a `.env`:

```
VITE_ADK_API_BASE=http://localhost:8000
# only needed if your FastAPI app mounts these routers under a prefix
VITE_ADK_API_PREFIX=
```

## Endpoint contract

`src/lib/api/client.ts` is the single place that knows about the backend.
Wired up against `api/chat_routes.py`, `api/ingest_routes.py`, and
`api/vector_ingest_routes.py` as given:

- **`POST /chat/stream`** — body `{ message, user_id, session_id }`. Response
  is **Server-Sent Events** (`text/event-stream`), not NDJSON — each frame is
  `event: <type>\ndata: <json>\n\n`. Three frame types are parsed:
  - `agent_step` → `{ agent, route, state_delta, partial_text, timestamp }`,
    one per node the graph executes. Drives the trace panel.
  - `final` → `{ session_id, answer, query_path, sql_executed, row_count, elapsed_ms }`,
    the terminal frame. `answer` becomes the AI bubble's content; the other
    fields render as the small metadata strip underneath it (route taken,
    row count, latency).
  - `error` → `{ message }`. Rendered inline in the AI bubble instead of a
    generic connection-failure message.
- **`POST /ingest`** (structured: CSV/XLSX) and **`POST /ingest/documents`**
  (PDF/MD/TXT) — multipart body with only a `file` field. `dataset_label` is
  a **querystring param**, not a form field (the FastAPI handlers only
  declare `file` via `File(...)`, so the plain `str | None` param binds from
  the query string). Both return a full `IngestionStatusResponse`
  (`job_id`, `file_name`, `status`, `current_step`, `progress_pct`,
  `rows_ingested`, `error`, …) immediately, so the UI seeds the job row from
  that response rather than waiting on the first poll.
- **`GET /ingest/status?job_id=...`** and **`GET /ingest/documents/status?job_id=...`**
  — separate per-kind polling routes; `job_id` is a query param, not a path
  segment. Polled every 1s until `status` is terminal.
- `IngestionStage`'s exact casing wasn't visible from the route code, so
  `useIngestion.ts` normalizes case-insensitively (matches on substrings like
  `fail`/`error`, `complet`/`done`, `process`/`running`, else `queued`). If
  your enum values are e.g. `"PENDING"` vs `"pending"` this just works either
  way — but check `normalizeStatus()` if a status ever renders as "queued"
  when it shouldn't.

If anything above drifts from the real backend, it's isolated to
`src/lib/api/client.ts` (endpoints, request/response shapes) and
`useIngestion.ts`'s `normalizeStatus` — nothing else in the app needs to
change.

## How the trace panel decides what to render

`state_delta` keys are pattern-matched in `TraceStep.tsx`:

- `generated_sql` / `reviewed_sql` → syntax-highlighted SQL block
- `execution_result` → a data table if it's a uniform array of records,
  otherwise a collapsible JSON tree
- `route` → the colored SQL/VECTOR fork badge, and it recolors the trace
  panel's spine from that point on
- anything else → falls through to the generic JSON tree

Agents named `delay_*` / `vector_delay_*` collapse to a small tick mark
instead of a full stepper row.

## Notes

- `user_id` is a UUID persisted in `localStorage`; `session_id` comes from
  the `final` frame's `session_id` field and is kept in `sessionStorage` for
  the tab.
- The "no data ingested yet → external_support" case isn't treated as an
  error. Since the `final` frame doesn't name an agent, the hook tracks the
  last `agent_step`'s agent name and flags the reply as a support fallback if
  it matches `/support/i` — this drives the badge above the AI bubble, not a
  red error state.
