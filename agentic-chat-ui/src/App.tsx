import { useState } from "react";
import { PanelLeftClose, PanelLeftOpen, Waypoints } from "lucide-react";
import { Sidebar } from "./components/Sidebar";
import { ChatPanel } from "./components/ChatPanel";
import { useChat } from "./hooks/useChat";

// useChat is instantiated once here and passed down isn't trivial since
// ChatPanel currently owns its own instance — lift it up so the sidebar's
// "new conversation" and session id stay in sync with the chat thread.
export default function App() {
  const chat = useChat();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden">
      <header className="flex h-12 shrink-0 items-center gap-2 border-b border-[var(--color-border-soft)] px-3">
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-text-muted)] hover:bg-[var(--color-surface-raised)]"
          aria-label="Toggle sidebar"
        >
          {sidebarOpen ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
        </button>
        <div className="flex items-center gap-1.5">
          <Waypoints size={15} className="text-[var(--color-accent-strong)]" />
          <span className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-wide">
            Ingest Console
          </span>
        </div>
        <span className="ml-auto rounded-full border border-[var(--color-border)] px-2 py-0.5 font-[family-name:var(--font-mono)] text-[10px] text-[var(--color-text-faint)]">
          agentic RAG
        </span>
      </header>

      <div className="flex min-h-0 flex-1">
        {sidebarOpen && (
          <Sidebar sessionId={chat.sessionId} onNewConversation={chat.startNewConversation} />
        )}
        <ChatPanel chat={chat} />
      </div>
    </div>
  );
}
