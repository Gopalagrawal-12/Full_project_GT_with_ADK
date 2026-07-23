import { useCallback, useRef, useState } from 'react';
import { streamChat } from '@/lib/api/client';
import { agentLeafName, getOrCreateUserId, isThrottleAgent, shortId } from '@/lib/utils';
import type { AgentTraceStep, ChatMessage, ChatSseEvent } from '@/types';

const SESSION_KEY = 'adk_console_session_id';

export function useAdkChat() {
  const userIdRef = useRef(getOrCreateUserId());
  const [sessionId, setSessionId] = useState<string | null>(() =>
    sessionStorage.getItem(SESSION_KEY)
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [traceSteps, setTraceSteps] = useState<AgentTraceStep[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const persistSessionId = useCallback((id: string) => {
    sessionStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || isStreaming) return;

      const userMsgId = shortId();
      const aiMsgId = shortId();

      setMessages((prev) => [
        ...prev,
        { id: userMsgId, role: 'user', content: message },
        { id: aiMsgId, role: 'ai', content: '', pending: true },
      ]);
      setTraceSteps([]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      // Tracks which agent last ran, so a support-fallback reply can be
      // flagged even though the `final` frame itself doesn't name an agent.
      let lastAgent: string | null = null;

      const applyEvent = (event: ChatSseEvent) => {
        if (event.type === 'agent_step') {
          const hasDelta = event.state_delta && Object.keys(event.state_delta).length > 0;
          lastAgent = event.agent;

          if (hasDelta) {
            const key = event.agent;
            const throttle = isThrottleAgent(event.agent);

            setTraceSteps((prev) => {
              const existingIdx = prev.findIndex((s) => s.rawAgentName === key && s.status === 'active');
              // A new agent showing up means whatever was previously active
              // just finished its step.
              const closed = prev.map((s) =>
                s.status === 'active' && s.rawAgentName !== key ? { ...s, status: 'complete' as const } : s
              );

              if (existingIdx >= 0) {
                return closed.map((s, i) =>
                  i === existingIdx
                    ? {
                        ...s,
                        delta: { ...s.delta, ...event.state_delta },
                        route: event.route ?? s.route,
                        time: event.timestamp,
                      }
                    : s
                );
              }

              const newStep: AgentTraceStep = {
                id: `${key}-${event.timestamp}-${shortId()}`,
                agentName: agentLeafName(event.agent),
                rawAgentName: key,
                route: event.route ?? null,
                delta: event.state_delta,
                status: 'active',
                time: event.timestamp,
                isThrottle: throttle,
              };
              return [...closed, newStep];
            });
          }

          if (event.partial_text) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiMsgId ? { ...m, content: m.content + event.partial_text, pending: false } : m
              )
            );
          }
        }

        if (event.type === 'final') {
          if (event.session_id && !sessionId) persistSessionId(event.session_id);

          const isSupportFallback = !!lastAgent && /support/i.test(lastAgent);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? {
                    ...m,
                    content: event.answer,
                    pending: false,
                    isSupportFallback,
                    summary: {
                      queryPath: event.query_path,
                      sqlExecuted: event.sql_executed,
                      rowCount: event.row_count,
                      elapsedMs: event.elapsed_ms,
                    },
                  }
                : m
            )
          );
        }

        if (event.type === 'error') {
          setMessages((prev) =>
            prev.map((m) => (m.id === aiMsgId ? { ...m, content: `Pipeline error: ${event.message}`, pending: false } : m))
          );
        }
      };

      try {
        await streamChat(message, userIdRef.current, sessionId, applyEvent, controller.signal);
      } catch (error) {
        console.error('Chat stream error:', error);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId
              ? { ...m, content: m.content || 'Connection to the agent backend failed. Check that it is running on localhost:8000.', pending: false }
              : m
          )
        );
      } finally {
        setTraceSteps((prev) => prev.map((s) => (s.status === 'active' ? { ...s, status: 'complete' } : s)));
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [sessionId, isStreaming, persistSessionId]
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    userId: userIdRef.current,
    sessionId,
    messages,
    traceSteps,
    isStreaming,
    sendMessage,
    stopStreaming,
  };
}
