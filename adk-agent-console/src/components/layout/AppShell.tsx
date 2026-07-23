import { useState } from 'react';
import { motion } from 'framer-motion';
import { Database, PanelRightClose, PanelRightOpen, Workflow } from 'lucide-react';
import { useAdkChat } from '@/hooks/useAdkChat';
import ChatPanel from '@/components/chat/ChatPanel';
import TracePanel from '@/components/trace/TracePanel';
import IngestionModal from '@/components/ingestion/IngestionModal';

export default function AppShell() {
  const chat = useAdkChat();
  const [tracePanelOpen, setTracePanelOpen] = useState(true);
  const [ingestOpen, setIngestOpen] = useState(false);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-canvas">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-hairline bg-panel/60 px-5 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-pulse/15 text-pulse">
            <Workflow className="h-4 w-4" />
          </div>
          <span className="font-semibold tracking-tight text-zinc-100">Agent Console</span>
          {chat.sessionId && (
            <span className="ml-2 rounded-full border border-hairline bg-panel-raised px-2 py-0.5 font-mono text-[11px] text-zinc-500">
              session · {chat.sessionId.slice(0, 8)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIngestOpen(true)}
            className="flex items-center gap-1.5 rounded-md border border-hairline bg-panel-raised px-3 py-1.5 text-sm text-zinc-300 transition hover:border-zinc-700 hover:text-zinc-100"
          >
            <Database className="h-3.5 w-3.5" />
            Ingest data
          </button>
          <button
            onClick={() => setTracePanelOpen((v) => !v)}
            aria-label={tracePanelOpen ? 'Collapse trace panel' : 'Expand trace panel'}
            className="flex h-8 w-8 items-center justify-center rounded-md border border-hairline bg-panel-raised text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-100"
          >
            {tracePanelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div
          className="flex min-h-0 flex-col transition-[width] duration-300 ease-out"
          style={{ width: tracePanelOpen ? '60%' : '100%' }}
        >
          <ChatPanel
            messages={chat.messages}
            isStreaming={chat.isStreaming}
            onSend={chat.sendMessage}
            onStop={chat.stopStreaming}
          />
        </div>

        {tracePanelOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: '40%', opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="min-h-0 shrink-0 border-l border-hairline bg-panel"
          >
            <TracePanel steps={chat.traceSteps} isStreaming={chat.isStreaming} />
          </motion.div>
        )}
      </div>

      <IngestionModal open={ingestOpen} onClose={() => setIngestOpen(false)} />
    </div>
  );
}
