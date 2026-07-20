"""
api/chat_routes.py
----------------------
POST /chat         -> runs the ADK Workflow graph end-to-end, returns one final answer.
POST /chat/stream    -> same pipeline, but streamed as Server-Sent Events so a frontend
                       can show live agent-by-agent progress (which agent is running,
                       what it wrote to state, which route it took) -- an ADK-web-ui-like
                       trace, without needing a custom ADK UI.

Owns the Runner + InMemorySessionService singletons, since they're specific
to the chat/agent-execution concern (as opposed to ingestion, which is pure
Postgres I/O and lives in ingest_routes.py / vector_ingest_routes.py).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from schemas.chat_schemas import ChatRequest, ChatResponse
from services.orchestrator import sql_rag_workflow

logger = logging.getLogger("adk_rag.api.chat_routes")
router = APIRouter()

APP_NAME = "adk_sql_rag"

session_service = InMemorySessionService()

# NOTE: Workflow graphs are not BaseAgent instances in google-adk >= 2.x, so
# they're wired into the Runner via `node=`, not `agent=`.
runner = Runner(
    app_name=APP_NAME,
    node=sql_rag_workflow,
    session_service=session_service,
)


async def _ensure_session(user_id: str, session_id: str) -> None:
    existing = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if existing is None:
        await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)


def _build_user_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def _extract_query_path(raw_path) -> str | None:
    if not raw_path:
        return None
    try:
        return json.loads(raw_path).get("path")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return str(raw_path).strip().upper() or None


def _extract_row_count(raw_exec) -> int | None:
    if not raw_exec:
        return None
    try:
        return json.loads(raw_exec).get("row_count")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    start = time.perf_counter()

    session_id = request.session_id or str(uuid.uuid4())
    await _ensure_session(request.user_id, session_id)

    final_text: str | None = None

    async for event in runner.run_async(
        user_id=request.user_id,
        session_id=session_id,
        new_message=_build_user_message(request.message),
    ):
        # Each node's LLM/function output arrives as a streamed Event. The
        # workflow's terminal nodes (query_visualization / vector_synthesis /
        # external_support) write state["final_answer"], but we defensively
        # also scan event content in case of partial/streamed text.
        if event.content and event.content.parts:
            text_parts = [p.text for p in event.content.parts if p.text]
            if text_parts and event.author in ("query_visualization", "vector_synthesis", "external_support"):
                final_text = "".join(text_parts)

    query_path: str | None = None
    generated_sql: str | None = None
    row_count: int | None = None

    session = await session_service.get_session(app_name=APP_NAME, user_id=request.user_id, session_id=session_id)
    if session is not None:
        state = session.state or {}
        final_text = final_text or state.get("final_answer")
        generated_sql = state.get("reviewed_sql")
        query_path = _extract_query_path(state.get("query_path"))
        row_count = _extract_row_count(state.get("execution_result"))

    if not final_text:
        raise HTTPException(status_code=502, detail="Pipeline completed without producing a final answer.")

    return ChatResponse(
        session_id=session_id,
        answer=final_text,
        query_path=query_path,  # type: ignore[arg-type]
        sql_executed=generated_sql,
        row_count=row_count,
        elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
    )


def _sse(event_type: str, payload: dict) -> str:
    """Formats one Server-Sent-Events frame."""
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


async def _stream_chat_events(request: ChatRequest, session_id: str) -> AsyncIterator[str]:
    """
    Wraps runner.run_async and re-emits every ADK Event as an SSE frame the
    frontend can render as a live agent trace:

      "agent_step"  -- one per node the graph executes. Carries:
                         agent        which agent/node just ran (event.node_info.path,
                                      falling back to event.author for plain LLM events)
                         route        the routing decision if this node was a router
                                      (route_by_classification / check_fallback)
                         state_delta  exactly what that node wrote to shared state --
                                      this IS "the agent's parameters/output" the ADK
                                      web UI shows, taken straight from event.actions
                         partial_text  any streamed text content from that step
      "final"        -- one terminal frame with the same shape as POST /chat's response.
      "error"         -- emitted (and the stream closed) if the pipeline raises.
    """
    start = time.perf_counter()
    final_text: str | None = None

    try:
        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=session_id,
            new_message=_build_user_message(request.message),
        ):
            agent_name = (
                event.node_info.path if event.node_info and event.node_info.path else event.author
            ) or "workflow"
            route = getattr(event.actions, "route", None)
            state_delta = getattr(event.actions, "state_delta", None) or {}
            text_parts = (
                [p.text for p in event.content.parts if p.text] if event.content and event.content.parts else []
            )
            partial_text = "".join(text_parts) or None

            if partial_text and agent_name in ("query_visualization", "vector_synthesis", "external_support"):
                final_text = partial_text

            yield _sse(
                "agent_step",
                {
                    "agent": agent_name,
                    "route": route,
                    "state_delta": state_delta,
                    "partial_text": partial_text,
                    "timestamp": event.timestamp,
                },
            )
    except Exception as exc:  # noqa: BLE001 - surface pipeline errors to the stream, don't 500 silently
        logger.exception("chat stream failed")
        yield _sse("error", {"message": str(exc)})
        return

    session = await session_service.get_session(app_name=APP_NAME, user_id=request.user_id, session_id=session_id)
    query_path: str | None = None
    generated_sql: str | None = None
    row_count: int | None = None
    if session is not None:
        state = session.state or {}
        final_text = final_text or state.get("final_answer")
        generated_sql = state.get("reviewed_sql")
        query_path = _extract_query_path(state.get("query_path"))
        row_count = _extract_row_count(state.get("execution_result"))

    yield _sse(
        "final",
        {
            "session_id": session_id,
            "answer": final_text or "The pipeline completed without producing a final answer.",
            "query_path": query_path,
            "sql_executed": generated_sql,
            "row_count": row_count,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
        },
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or str(uuid.uuid4())
    await _ensure_session(request.user_id, session_id)

    return StreamingResponse(
        _stream_chat_events(request, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
