import { useEffect, useRef, useState } from 'react';
import { ArrowUp, Square, Sparkles } from 'lucide-react';
import ChatMessage from './ChatMessage';
import type { ChatMessage as ChatMessageType } from '@/types';

interface ChatPanelProps {
  messages: ChatMessageType[];
  isStreaming: boolean;
  onSend: (query: string) => void;
  onStop: () => void;
}

export default function ChatPanel({ messages, isStreaming, onSend, onStop }: ChatPanelProps) {
  const [draft, setDraft] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const submit = () => {
    if (!draft.trim() || isStreaming) return;
    onSend(draft.trim());
    setDraft('');
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} className="scroll-thin flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8">
            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-hairline bg-panel/60 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-hairline bg-panel-raised px-3 py-2 focus-within:border-pulse-dim">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Ask about your data…"
            rows={1}
            className="max-h-40 flex-1 resize-none bg-transparent py-1.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
          />
          {isStreaming ? (
            <button
              onClick={onStop}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-zinc-700 text-zinc-200 transition hover:bg-zinc-600"
              aria-label="Stop generating"
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!draft.trim()}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-pulse text-white transition enabled:hover:bg-pulse/90 disabled:opacity-30"
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
        </div>
        <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-zinc-600">
          Enter to send · Shift+Enter for a new line
        </p>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-pulse/10 text-pulse">
        <Sparkles className="h-5 w-5" />
      </div>
      <h2 className="text-lg font-medium text-zinc-200">Ask something about your data</h2>
      <p className="max-w-sm text-sm text-zinc-500">
        Every step the pipeline takes — routing, SQL generation, retrieval — streams live in the
        trace panel on the right.
      </p>
    </div>
  );
}
