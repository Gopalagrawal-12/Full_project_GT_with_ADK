// ---------------------------------------------------------------------------
// Types for the Ingestion + Agentic Chat backend.
//
// NOTE ON ASSUMPTIONS: the spec provided fully described Endpoints 3 & 4
// (CSV ingest + document ingest, both job/poll shaped) but Endpoints 1 & 2
// (`/chat` and `/chat/stream`) were referenced only indirectly (session_id,
// user_id, trace with node state_delta, routing to sql/vector/external_
// support). The shapes below are a best-effort, clearly-isolated guess —
// see `api/client.ts` for the single place to adjust field names once the
// real backend contract is confirmed. Everything else in the app consumes
// these types, so fixing them here fixes the whole app.
// ---------------------------------------------------------------------------

export type IngestStepCsv =
  | "idle"
  | "parsing_file"
  | "validating_rows"
  | "inserting_data_rows"
  | "done";

export type IngestStepDoc =
  | "idle"
  | "parsing_file"
  | "chunking"
  | "embedding"
  | "storing"
  | "done";

export type JobStatus = "idle" | "processing" | "completed" | "failed";

export interface IngestJob {
  job_id: string;
  status: JobStatus;
  current_step: IngestStepCsv | IngestStepDoc | string;
  progress_pct: number;
  file_name: string | null;
  rows_ingested: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export type IngestKind = "csv" | "document";

// --- Chat -------------------------------------------------------------

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: number;
  trace?: TraceStep[];
  routedTo?: string | null;
  pending?: boolean;
  error?: string | null;
}

/** One node execution in the agent graph, as surfaced in a trace. */
export interface TraceStep {
  node: string;
  status?: "ok" | "error" | "running";
  /** Backend's partial-state diff produced by this node, e.g. routing
   *  decision, retrieved rows, classification confidence, etc. */
  state_delta?: Record<string, unknown>;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
}

export interface ChatRequest {
  session_id: string;
  user_id: string;
  message: string;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  routed_to?: string | null;
  trace?: TraceStep[];
}

/** Normalized shape the UI works with, produced from whichever raw SSE
 *  event shape the backend actually sends (see parseSseEvent in client.ts). */
export type ChatStreamEvent =
  | { type: "trace_step"; step: TraceStep }
  | { type: "token"; content: string }
  | { type: "message"; content: string }
  | { type: "routing"; routedTo: string }
  | { type: "done"; sessionId?: string }
  | { type: "error"; message: string };
