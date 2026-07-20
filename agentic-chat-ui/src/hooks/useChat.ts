import { useCallback, useRef, useState } from "react";
import { ApiError, sendChat, streamChat } from "../api/client";
import { getSessionId, getUserId, resetSessionId } from "../lib/identity";
import type { ChatMessage, TraceStep } from "../types/api";

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState(getSessionId());
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingSupported, setStreamingSupported] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  const updateMessage = useCallback(
    (id: string, patch: Partial<ChatMessage>) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...patch } : m))
      );
    },
    []
  );

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      const userMsg: ChatMessage = {
        id: newId(),
        role: "user",
        content: trimmed,
        createdAt: Date.now(),
      };
      const assistantId = newId();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: Date.now(),
        pending: true,
        trace: [],
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      const payload = { session_id: sessionId, user_id: getUserId(), message: trimmed };
      const trace: TraceStep[] = [];

      if (streamingSupported) {
        const controller = new AbortController();
        abortRef.current = controller;
        try {
          let content = "";
          await streamChat(
            payload,
            (evt) => {
              if (evt.type === "trace_step") {
                trace.push(evt.step);
                updateMessage(assistantId, { trace: [...trace] });
              } else if (evt.type === "token") {
                content += evt.content;
                updateMessage(assistantId, { content, pending: true });
              } else if (evt.type === "message") {
                content = evt.content;
                updateMessage(assistantId, { content, pending: true });
              } else if (evt.type === "routing") {
                updateMessage(assistantId, { routedTo: evt.routedTo });
              } else if (evt.type === "error") {
                updateMessage(assistantId, {
                  error: evt.message,
                  pending: false,
                });
              } else if (evt.type === "done") {
                updateMessage(assistantId, { pending: false });
              }
            },
            controller.signal
          );
          updateMessage(assistantId, { pending: false });
        } catch (err) {
          if ((err as Error).name === "AbortError") {
            updateMessage(assistantId, { pending: false });
          } else if (err instanceof ApiError && err.status === 404) {
            // Streaming endpoint not available on this backend deployment —
            // fall back to the non-streaming /chat endpoint transparently.
            setStreamingSupported(false);
            await fallbackToNonStreaming(assistantId);
          } else {
            updateMessage(assistantId, {
              pending: false,
              error: (err as Error).message ?? "Something went wrong.",
            });
          }
        } finally {
          setIsStreaming(false);
          abortRef.current = null;
        }
      } else {
        await fallbackToNonStreaming(assistantId);
        setIsStreaming(false);
      }

      async function fallbackToNonStreaming(id: string) {
        try {
          const res = await sendChat(payload);
          updateMessage(id, {
            content: res.message,
            trace: res.trace ?? [],
            routedTo: res.routed_to ?? null,
            pending: false,
          });
        } catch (err) {
          updateMessage(id, {
            pending: false,
            error: (err as Error).message ?? "Something went wrong.",
          });
        }
      }
    },
    [isStreaming, sessionId, streamingSupported, updateMessage]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const startNewConversation = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setSessionId(resetSessionId());
    setIsStreaming(false);
  }, []);

  return {
    messages,
    sessionId,
    isStreaming,
    send,
    stop,
    startNewConversation,
  };
}
