import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square, MessageSquareDashed } from "lucide-react";
import type { useChat } from "../hooks/useChat";
import { MessageBubble } from "./MessageBubble";

export function ChatPanel({ chat }: { chat: ReturnType<typeof useChat> }) {
  const { messages, isStreaming, send, stop } = chat;
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const submit = () => {
    if (!input.trim() || isStreaming) return;
    send(input);
    setInput("");
  };

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-5 sm:px-8">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-[var(--color-border-soft)] bg-[var(--color-bg)] px-4 py-3 sm:px-8">
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-2 focus-within:border-[var(--color-accent)] transition-colors">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask about your ingested data…"
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-[13.5px] text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] outline-none"
          />
          {isStreaming ? (
            <button
              onClick={stop}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-border-soft)] transition-colors"
              aria-label="Stop"
            >
              <Square size={13} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!input.trim()}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--color-accent)] text-[#0a0d13] transition-opacity disabled:opacity-30"
              aria-label="Send"
            >
              <ArrowUp size={15} strokeWidth={2.5} />
            </button>
          )}
        </div>
        <p className="mx-auto mt-1.5 max-w-3xl text-center text-[10.5px] text-[var(--color-text-faint)]">
          Enter to send · Shift+Enter for a new line
        </p>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[var(--color-surface-raised)] ring-1 ring-[var(--color-border)]">
        <MessageSquareDashed size={19} className="text-[var(--color-text-faint)]" />
      </div>
      <div>
        <p className="font-[family-name:var(--font-display)] text-[14px] font-medium text-[var(--color-text)]">
          Nothing asked yet
        </p>
        <p className="mt-1 max-w-xs text-[12px] leading-relaxed text-[var(--color-text-muted)]">
          Ingest a CSV or document on the left, then ask a question here — or
          just ask; the agent will say if nothing's been ingested yet.
        </p>
      </div>
    </div>
  );
}
