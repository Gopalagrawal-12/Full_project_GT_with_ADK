// --- Chat / trace: mirrors api/chat_routes.py's SSE frames exactly ---
//
// POST /chat/stream emits three frame types, each as
//   event: <type>\ndata: <json>\n\n
//
// agent_step  — one per node the graph executes
// final       — one terminal frame, same shape as POST /chat's ChatResponse
// error       — emitted (and the stream closed) if the pipeline raises

export interface AgentStepEvent {
  type: 'agent_step';
  agent: string;
  route?: string | null;
  state_delta: Record<string, any>;
  partial_text?: string | null;
  timestamp: number;
}

export interface FinalEvent {
  type: 'final';
  session_id: string;
  answer: string;
  query_path?: string | null;
  sql_executed?: string | null;
  row_count?: number | null;
  elapsed_ms: number;
}

export interface ErrorEvent {
  type: 'error';
  message: string;
}

export type ChatSseEvent = AgentStepEvent | FinalEvent | ErrorEvent;

export type AgentStatus = 'complete' | 'active';

// One row in the Live Agent Trace stepper — one per unique agent seen so far
// in the current turn.
export interface AgentTraceStep {
  id: string;
  agentName: string;
  rawAgentName: string;
  route?: string | null;
  delta: Record<string, any>;
  status: AgentStatus;
  time: number;
  isThrottle: boolean;
}

// Surfaced under the AI bubble once the `final` frame lands — the same
// query_path / sql_executed / row_count / elapsed_ms fields as ChatResponse.
export interface TurnSummary {
  queryPath?: string | null;
  sqlExecuted?: string | null;
  rowCount?: number | null;
  elapsedMs?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  content: string;
  isSupportFallback?: boolean;
  pending?: boolean;
  summary?: TurnSummary;
}

// --- Ingestion: mirrors schemas/ingestion_schemas.IngestionStatusResponse ---

export type IngestionKind = 'structured' | 'document';

// UI-normalized status; the raw API status string (whatever casing
// IngestionStage uses) is mapped onto this in lib/api/client.ts.
export type IngestionStatus = 'queued' | 'running' | 'complete' | 'error';

export interface IngestionJob {
  jobId: string;
  kind: IngestionKind;
  fileName: string;
  status: IngestionStatus;
  progressPct: number;
  currentStep: string;
  rowsIngested?: number | null;
  error?: string;
}

// Raw shape returned by POST /ingest, POST /ingest/documents,
// GET /ingest/status, and GET /ingest/documents/status.
export interface IngestionStatusResponseApi {
  job_id: string;
  file_name: string;
  status: string;
  current_step: string;
  progress_pct: number;
  rows_ingested?: number | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

