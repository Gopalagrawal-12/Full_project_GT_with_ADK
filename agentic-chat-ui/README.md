# Ingest Console

A chat UI for an agentic RAG backend: ask questions, watch the agent graph's
reasoning (routing, SQL vs. vector decisions, retrieved rows) in a
collapsible trace panel, and ingest CSVs / documents with live progress bars.

## Stack

Vite + React + TypeScript + Tailwind v4 + lucide-react. No heavier framework
needed for 6 endpoints — all backend calls live in `src/api/client.ts`.

## Run it

```bash
npm install
cp .env.example .env   # set VITE_API_BASE_URL, or leave blank for same-origin
npm run dev
```

You can also set the base URL at runtime from the **Backend connection**
panel in the sidebar (stored in `localStorage`, overrides the env value) —
handy for pointing the same build at different environments without a rebuild.

## Where things live

```
src/
  api/client.ts        typed client for all 6 endpoints (the only place that calls fetch)
  hooks/useChat.ts      message list, streaming, non-streaming fallback
  hooks/useIngestJob.ts upload + 1s status polling for both ingest kinds
  lib/identity.ts       stable user_id + per-conversation session_id (localStorage)
  components/
    ChatPanel.tsx        message thread + composer
    MessageBubble.tsx     one message, with a "Show trace" toggle
    TracePanel.tsx        the pipeline ladder (agent graph steps, expandable state_delta)
    UploadPanel.tsx        generic ingest panel, used for both CSV and documents
    Sidebar.tsx             connection settings, both upload panels, session card
```

## Design notes

Dark "operator console" aesthetic (`#0a0d13` base, `#6d8bff` accent) rather
than a generic light chat UI, since this is a debugging/power-user tool as
much as a chat client. The trace panel is the intentional signature
element: agent graph nodes really do execute in sequence with a real
branching decision (SQL vs. VECTOR), so a connected step ladder with
per-node color coding (violet = classification/routing, blue = retrieval,
green = generation, amber = support fallback) encodes real information
rather than decorating it. Monospace (`IBM Plex Mono`) is used specifically
for IDs, `current_step` labels, and raw `state_delta` JSON — anywhere the
value is "backend truth" rather than prose.

## A note on `/chat` and `/chat/stream`

The spec text I was given fully pinned down Endpoints 3 & 4 (ingest job +
polling) but only indirectly described `/chat` and `/chat/stream` — via the
requirement to send `session_id`/`user_id`, and the mention that a trace's
`query_classification` step exposes a `state_delta` explaining the SQL vs.
VECTOR routing decision. I filled in the gaps as follows; **please check
these against your actual backend and adjust `src/api/client.ts` /
`src/types/api.ts` if they differ** (everything else in the app is written
against the types in `types/api.ts`, so fixing the shapes there fixes the
whole app):

- `POST /api/v1/chat` (non-streaming): body `{ session_id, user_id, message }`,
  response `{ session_id, message, routed_to?, trace? }` where `trace` is
  `TraceStep[]` (`{ node, state_delta, status?, duration_ms? }`).
- `POST /api/v1/chat/stream`: same request body; response is treated as
  either SSE (`data: {...}\n\n`) or newline-delimited JSON — the client
  auto-detects both. Each event is normalized into one of `trace_step`,
  `token`, `message`, `routing`, `done`, `error` (see
  `normalizeStreamEvent` in `client.ts`). Adjust the field names it looks
  for (`type`/`event`, `content`/`delta`, `node`, `state_delta`,
  `routed_to`) to match your actual event schema.
- If `/chat/stream` 404s, `useChat` transparently falls back to
  `POST /api/v1/chat` for the rest of the session — so the UI works even if
  streaming isn't deployed yet.
- The "nothing ingested yet" case isn't special-cased anywhere: it's just
  rendered as a normal assistant message, with `routed_to: "external_support"`
  shown as a small routing badge on the trace panel if the backend sends it.

## Building for production

```bash
npm run build   # outputs to dist/
npm run preview # sanity-check the production build locally
```
