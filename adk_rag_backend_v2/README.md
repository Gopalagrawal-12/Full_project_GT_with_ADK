# Multi-Agent ADK Backend — Text-to-SQL + Vector RAG, for any dataset

A general-purpose analytics backend: point it at ANY tabular data (CSV today,
Excel/other formats are a one-file swap — see `api/ingest_routes.py`) and ANY
document corpus (Markdown out of the box, PDF/DOCX/PPTX/XLSX/HTML with the
optional `docling` extra), ask questions in plain English, and a 10-agent
graph decides whether the answer lives in structured rows or in unstructured
text, retrieves it, and reasons over it like an analyst — not a template
matcher. Nothing in the schema, prompts, or routing logic assumes a specific
business domain.

Verified against **`google-adk` v2.4.0** (built and import-tested against the
actual installed package — including a full 14-node graph build with real
`Workflow`/`Agent`/`node` objects, not assumed from memory).

## Why "a brain, not a pipeline"

Most text-to-SQL demos are a straight line: question -> SQL -> rows -> answer.
That breaks the moment a question needs more than one logical hop, or doesn't
map cleanly to a table at all. This backend is built around three ideas
instead:

1. **Decompose before you answer.** `query_understanding_agent` doesn't just
   extract keywords — it explicitly identifies when a question needs multiple
   steps (`sub_questions`) and flags genuine ambiguity against the actual
   ingested schema (`ambiguous` + `clarification_question`) rather than
   guessing silently.
2. **Classify with reasoning, not a coin flip.** `query_classification_agent`
   emits a confidence score and a one-line justification for SQL vs VECTOR,
   grounded in what's actually been ingested (`fetch_database_schema` reports
   on BOTH the tabular data lake and the document corpus every single run).
3. **Synthesize like an analyst, not a summarizer.** `vector_synthesis_agent`
   is explicitly instructed to reconcile agreement/disagreement across
   multiple retrieved chunks, cite sources inline, and say what's missing —
   never flatten five sources into one falsely-confident paragraph.
4. **Understand the data before anyone asks a question.** Nobody hand-writes
   column metadata. At ingestion time, `generate_column_metadata`
   (`api/ingest_routes.py`) shows an LLM (Groq) a real sample of the parsed
   CSV and asks it to describe the table and each column — semantics,
   synonyms/jargon, and SQL-generation hints — before a single question is
   ever asked. `query_generation_agent` is explicitly instructed to match a
   user's terminology to the right column via those synonyms rather than
   requiring an exact name match. If that LLM call fails for any reason, it
   falls back to bare column names/dtypes rather than blocking ingestion.

## File layout — one responsibility per file

```
main.py                              FastAPI app, lifespan, CORS, router mount
requirements.txt

schemas/
  chat_schemas.py                    ChatRequest, ChatResponse
  ingestion_schemas.py               IngestionStage, IngestionStatusResponse (shared by both ingestion pipelines)
  state_schemas.py                   ParsedIntent, QueryClassification, GeneratedSQL, SQLExecutionResult,
                                      RetrievedChunk, VectorRetrievalResult, FinalAnswer

tools/                                pure infrastructure, no LLM logic
  schema_tool.py                     fetch_database_schema() -- grounds every agent in BOTH data surfaces
  sql_execution_tool.py               execute_sql()            -- SQL branch, read-only + guarded
  chunker.py                          create_chunker()          -- Docling HybridChunker, graceful fallback to SimpleChunker
  embedder.py                          create_embedder()         -- OpenAI-compatible client (Ollama by default)
  vector_search_tool.py                 vector_search()           -- pgvector cosine similarity search

agents/                               one micro-agent per file, 10 total
  query_understanding_agent.py        1. intent extraction + multi-hop decomposition + ambiguity detection
  query_classification_agent.py        2. reasoned SQL vs VECTOR routing decision (JSON, with confidence)
  time_lag_agent.py                     3. MoM/YoY CTE structural guidance
  query_generation_agent.py              4. writes the SQL (mandatory laws baked into the prompt)
  query_review_agent.py                   5. audits the SQL for precision/correctness
  query_execution_agent.py                 6. binds execute_sql, runs it
  query_visualization_agent.py              7. rows -> natural language, blind-trusts pre-filtered data
  vector_retrieval_agent.py                  8. reformulates the question for retrieval, runs vector_search
  vector_synthesis_agent.py                   9. chunks -> cited, analyst-style natural-language answer
  external_support_agent.py                   10. shared fallback handler for both branches

services/
  graph_nodes.py                     load_schema_context, route_by_classification (JSON-aware), check_fallback (shared by both branches)
  orchestrator.py                     build_sql_rag_workflow() -- assembles the 14-node graph
  vector_ingestion_service.py           chunk -> embed -> store pipeline for the document/RAG branch

api/
  ingest_routes.py                   POST /ingest, GET /ingest/status               (tabular data lake)
  vector_ingest_routes.py             POST /ingest/documents, GET /ingest/documents/status  (document corpus)
  chat_routes.py                       POST /chat, POST /chat/stream (SSE agent trace)
  router.py                             combines all three into one APIRouter

utils/
  db_pool.py                         init_pool / close_pool / get_pool (asyncpg)
  db_schema_bootstrap.py              ensure_schema() -- idempotent DDL for BOTH storage subsystems
  providers.py                         embedding backend config (Ollama by default, swap 3 env vars for OpenAI/Azure/etc.)
```

Every `__init__.py` re-exports its package's public names (`from agents import
query_understanding_agent`), but every implementation still lives in its own
single-purpose file.

## The 14-node graph (as actually built and inspected)

```
START -> load_schema_context -> query_understanding -> query_classification
      -> route_by_classification
           SQL    -> time_lag -> query_generation -> query_review
                     -> query_execution -> query_visualization ---\
                                                                     -> check_fallback
           VECTOR -> vector_retrieval -> vector_synthesis --------/
                                                                       NEEDS_SUPPORT -> external_support  [terminal]
                                                                       (default)     -> [terminal, final_answer already set]
```

`check_fallback` is a single shared safety-valve node reached by BOTH
branches — a genuinely converging graph, not two independent pipelines bolted
together. It checks `execution_result`, `vector_retrieval_result`, and
`final_answer` uniformly, so the fallback behavior is identical regardless of
which path answered the question.

`load_schema_context`, `route_by_classification`, and `check_fallback` are
plain Python `@node` functions (not LLM agents) — cheap glue that reads/writes
`ctx.state` and emits routing signals for the `RoutingMap` branches.

## State handoff contract

| Key | Writer | Type |
|---|---|---|
| `db_schema_summary` | `load_schema_context` | str — cheap overview (table/doc names, column names, one-line summaries) |
| `db_schema_detail` | `load_relevant_schema_detail` | str — SQL-branch only; full per-column metadata, filtered to relevant columns |
| `parsed_intent` | `query_understanding_agent` | JSON matching `ParsedIntent` (incl. `sub_questions`, `ambiguous`) |
| `query_path` | `query_classification_agent` | JSON matching `QueryClassification` (`path`, `confidence`, `reason`) |
| `time_series_hint` | `time_lag_agent` | str (`"NONE"` or CTE guidance) |
| `generated_sql` | `query_generation_agent` | raw SQL |
| `reviewed_sql` | `query_review_agent` | audited SQL |
| `execution_result` | `query_execution_agent` | JSON from `execute_sql` |
| `vector_retrieval_result` | `vector_retrieval_agent` | JSON from `vector_search` |
| `final_answer` | `query_visualization_agent` / `vector_synthesis_agent` / `external_support_agent` | str |

The API layer only ever reads `final_answer` off the session — it doesn't
care which branch produced it.

## Live agent trace (ADK-web-ui-like visibility)

`POST /api/v1/chat/stream` streams Server-Sent Events, one `agent_step` frame
per node the graph actually executes, straight from the ADK `Event` objects
`runner.run_async` yields:

```
event: agent_step
data: {"agent": "query_understanding", "route": null,
       "state_delta": {"parsed_intent": "{...}"} , "partial_text": null,
       "timestamp": 1737300000.123}

event: agent_step
data: {"agent": "route_by_classification", "route": "SQL",
       "state_delta": {}, "partial_text": null, "timestamp": 1737300000.456}

...

event: final
data: {"session_id": "...", "answer": "...", "query_path": "SQL",
       "sql_executed": "SELECT ...", "row_count": 12, "elapsed_ms": 842.1}
```

`agent` is the node currently executing (`event.node_info.path`, falling back
to `event.author`). `state_delta` is exactly what that node wrote to shared
state — this is the "agent's parameters/output" a UI panel would show, taken
directly from `event.actions.state_delta`. `route` is populated only on the
two routing nodes. This is enough to build an ADK-web-ui-style live trace
panel without a custom ADK UI — see the frontend integration prompt below.

## Running it

```bash
pip install -r requirements.txt
# optional, for rich document parsing + semantic chunking:
# pip install docling transformers pandas

export POSTGRES_HOST=localhost POSTGRES_DB=adk_rag POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
export GOOGLE_API_KEY=...                       # or ADC, per your google-adk model provider setup
export GROQ_API_KEY=...                          # used only at ingestion time, for auto column-metadata generation
export EMBEDDING_BASE_URL=http://localhost:11434/v1   # Ollama by default; point at OpenAI/Azure to swap
export EMBEDDING_MODEL=nomic-embed-text
uvicorn main:app --reload --port 8000
```

`ensure_schema()` runs `CREATE EXTENSION IF NOT EXISTS vector` plus
`CREATE TABLE IF NOT EXISTS` for `file_metadata`, `data_rows`, `documents`,
and `chunks` on startup. If pgvector isn't installed on your Postgres
instance, the tabular/SQL branch still boots fine — only the vector branch
will error until the extension is available.

Uploading a CSV never requires the caller to describe its columns —
`generate_column_metadata` in `api/ingest_routes.py` does that automatically
via Groq (`GROQ_METADATA_MODEL`, default `llama-3.1-8b-instant`) from a
sample of the actual parsed rows, and stores the result in
`file_metadata.columns` for every downstream agent to read.

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/ingest` | Upload a CSV -> background job into the tabular data lake |
| GET  | `/api/v1/ingest/status?job_id=...` | Poll tabular ingestion progress |
| POST | `/api/v1/ingest/documents` | Upload a document -> background chunk+embed+store job |
| GET  | `/api/v1/ingest/documents/status?job_id=...` | Poll document ingestion progress |
| POST | `/api/v1/chat` | Ask a question, get one final `ChatResponse` |
| POST | `/api/v1/chat/stream` | Same, streamed as SSE with a live per-agent trace |
| GET  | `/health` | Liveness check |

Full request/response schemas: `schemas/chat_schemas.py`,
`schemas/ingestion_schemas.py`, or just hit `/docs` (FastAPI's autogenerated
Swagger UI) once the server is running.

## Known gaps to fill in next (intentionally left as follow-ups)

- **Multi-hop execution**: `query_understanding_agent` already decomposes
  questions into `sub_questions`, but the graph doesn't yet loop over them —
  today it answers the primary question in one pass. Wiring an iterative
  sub-question loop is the natural next step (the `Workflow` node schema
  exposes a `retry_config`/dynamic-node-scheduling surface that fits this).
- **Ingestion parsers**: tabular ingestion (`api/ingest_routes.py`) uses
  stdlib `csv`; document ingestion (`services/vector_ingestion_service.py`)
  accepts `.md`/`.txt` natively and everything else via the optional
  `docling` extra. Swap in `pandas`/`openpyxl` for richer tabular formats.
- **Ingestion status store**: both ingestion routers use in-memory dicts —
  fine for one instance, needs Redis/DB-backed tracking behind a load
  balancer.
- **Auth**: no auth middleware yet; `user_id` is caller-supplied and trusted.

## How agents actually see state (this matters, and was a real bug once)

ADK only substitutes state into a prompt via literal `{key}` placeholders in
the `instruction` string — see `google.adk.utils.instructions_utils.
inject_session_state`, which regex-scans for `{...}` and looks each name up
in `ctx.session.state`. Writing `state.foo` as plain English prose does
**nothing** — it doesn't get substituted, and the LLM just sees the literal
text "state.foo". Every agent instruction in `agents/*.py` uses real
`{key}` / optional `{key?}` placeholders for exactly this reason — verified
by round-tripping `inject_session_state` directly against a fake session
state before trusting it in the graph.

### Context-window discipline

Every agent also sets `include_contents="none"` — it does not inherit prior
conversation/event history, only its own instruction (with state substituted)
plus whatever tool calls it makes. Combined with a two-tier schema grounding
strategy, each agent gets exactly the data it needs and nothing more:

| Grounding | Cost | Used by | Contains |
|---|---|---|---|
| `db_schema_summary` (`fetch_schema_overview`) | cheap | `query_understanding`, `query_classification` | table/document names, column **names only**, one-line table summaries |
| `db_schema_detail` (`fetch_schema_relevant_detail`) | expensive, on-demand | `query_generation` only | full per-column description/synonyms/sql_hints — but ONLY for columns matching the question's entities/metrics; every other column is a one-line stub |

`db_schema_detail` is computed by `services/graph_nodes.py::
load_relevant_schema_detail`, inserted into the graph right after `time_lag`
and right before `query_generation` — i.e. only on the SQL branch, and only
once `parsed_intent` exists to filter against. A VECTOR-branch question never
pays for it at all.

## Frontend integration

See `FRONTEND_INTEGRATION_PROMPT.md` — a copy-pasteable prompt for building a
frontend (in any framework, on any LLM coding assistant) against this API,
including a live ADK-web-ui-style agent trace panel.
