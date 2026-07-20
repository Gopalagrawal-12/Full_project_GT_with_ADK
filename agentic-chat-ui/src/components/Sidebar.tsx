import { useState } from "react";
import { Plug, RotateCcw, Copy, Check } from "lucide-react";
import { UploadPanel } from "./UploadPanel";
import { getBaseUrl, setBaseUrl } from "../api/client";
import { getUserId } from "../lib/identity";

export function Sidebar({
  sessionId,
  onNewConversation,
}: {
  sessionId: string;
  onNewConversation: () => void;
}) {
  return (
    <aside className="flex h-full w-[300px] shrink-0 flex-col gap-3 overflow-y-auto border-r border-[var(--color-border-soft)] bg-[var(--color-bg)] p-3">
      <ConnectionSettings />

      <UploadPanel
        kind="csv"
        title="Structured data"
        hint="CSV rows for SQL-style querying."
        accept=".csv"
      />
      <UploadPanel
        kind="document"
        title="Documents"
        hint="Markdown, text, or office docs for semantic search."
        accept=".md,.txt,.pdf,.docx,.pptx,.xlsx,.html"
      />

      <SessionCard sessionId={sessionId} onNewConversation={onNewConversation} />
    </aside>
  );
}

function ConnectionSettings() {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState(getBaseUrl());
  const [saved, setSaved] = useState(false);

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 text-left"
      >
        <Plug size={13} className="text-[var(--color-text-faint)]" />
        <span className="font-[family-name:var(--font-display)] text-[12.5px] font-semibold text-[var(--color-text)]">
          Backend connection
        </span>
      </button>
      {open && (
        <div className="fade-up mt-2.5 flex flex-col gap-2">
          <label className="text-[10.5px] font-medium uppercase tracking-wide text-[var(--color-text-faint)]">
            Base URL
          </label>
          <div className="flex gap-1.5">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api.example.com"
              className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2 py-1.5 font-[family-name:var(--font-mono)] text-[11px] text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
            />
            <button
              onClick={() => {
                setBaseUrl(url);
                setSaved(true);
                setTimeout(() => setSaved(false), 1200);
              }}
              className="shrink-0 rounded-md bg-[var(--color-accent)] px-2.5 text-[11px] font-medium text-[#0a0d13]"
            >
              {saved ? "Saved" : "Save"}
            </button>
          </div>
          <p className="text-[10.5px] leading-snug text-[var(--color-text-faint)]">
            Leave blank to use the same origin this app is served from (e.g.
            behind a reverse proxy).
          </p>
        </div>
      )}
      {!open && (
        <p className="mt-1 truncate font-[family-name:var(--font-mono)] text-[10.5px] text-[var(--color-text-faint)]">
          {getBaseUrl() || "same origin"}
        </p>
      )}
    </div>
  );
}

function SessionCard({
  sessionId,
  onNewConversation,
}: {
  sessionId: string;
  onNewConversation: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const userId = getUserId();

  const copy = (val: string) => {
    navigator.clipboard.writeText(val).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  };

  return (
    <div className="mt-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex flex-col gap-2 font-[family-name:var(--font-mono)] text-[10.5px]">
        <IdRow label="user_id" value={userId} onCopy={copy} copied={copied} />
        <IdRow label="session_id" value={sessionId} onCopy={copy} copied={copied} />
      </div>
      <button
        onClick={onNewConversation}
        className="mt-2.5 flex w-full items-center justify-center gap-1.5 rounded-md border border-[var(--color-border)] py-1.5 text-[11.5px] font-medium text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent-strong)] transition-colors"
      >
        <RotateCcw size={12} />
        New conversation
      </button>
    </div>
  );
}

function IdRow({
  label,
  value,
  onCopy,
  copied,
}: {
  label: string;
  value: string;
  onCopy: (v: string) => void;
  copied: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--color-text-faint)]">{label}</span>
      <button
        onClick={() => onCopy(value)}
        className="flex min-w-0 items-center gap-1 rounded px-1 py-0.5 text-[var(--color-text-muted)] hover:bg-[var(--color-border)]"
        title={value}
      >
        <span className="max-w-[130px] truncate">{value}</span>
        {copied ? <Check size={10} /> : <Copy size={10} />}
      </button>
    </div>
  );
}
