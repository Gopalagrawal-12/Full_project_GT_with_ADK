import { useState } from "react";
import { Sparkles, AlertTriangle, ListTree } from "lucide-react";
import type { ChatMessage } from "../types/api";
import { TracePanel } from "./TracePanel";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const [showTrace, setShowTrace] = useState(false);
  const isUser = message.role === "user";
  const hasTrace = (message.trace?.length ?? 0) > 0;

  if (isUser) {
    return (
      <div className="fade-up flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-[var(--color-accent)] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-[#0a0d13]">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="fade-up flex gap-2.5">
      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-surface-raised)] ring-1 ring-[var(--color-border)]">
        <Sparkles size={12} className="text-[var(--color-accent-strong)]" />
      </div>
      <div className="min-w-0 max-w-[80%] flex-1">
        <div className="rounded-2xl rounded-tl-sm border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-[var(--color-text)]">
          {message.pending && !message.content ? (
            <ThinkingDots />
          ) : (
            <span className="whitespace-pre-wrap">{message.content}</span>
          )}
          {message.error && (
            <div className="mt-2 flex items-center gap-1.5 text-[12px] text-[var(--color-danger)]">
              <AlertTriangle size={13} />
              {message.error}
            </div>
          )}
        </div>

        {hasTrace && (
          <div className="mt-1 flex items-center gap-2 pl-0.5">
            <button
              onClick={() => setShowTrace((v) => !v)}
              className="flex items-center gap-1 text-[11px] font-medium text-[var(--color-text-faint)] hover:text-[var(--color-accent-strong)] transition-colors"
            >
              <ListTree size={11} />
              {showTrace ? "Hide" : "Show"} trace · {message.trace!.length} step
              {message.trace!.length === 1 ? "" : "s"}
            </button>
          </div>
        )}
        {hasTrace && showTrace && (
          <TracePanel trace={message.trace!} routedTo={message.routedTo} />
        )}
      </div>
    </div>
  );
}

function ThinkingDots() {
  return (
    <span className="flex items-center gap-1 py-0.5">
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-text-faint)] pulse-dot" style={{ animationDelay: "0ms" }} />
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-text-faint)] pulse-dot" style={{ animationDelay: "150ms" }} />
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-text-faint)] pulse-dot" style={{ animationDelay: "300ms" }} />
    </span>
  );
}
