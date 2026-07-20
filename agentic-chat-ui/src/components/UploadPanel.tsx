import { useRef, useState } from "react";
import { UploadCloud, FileText, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { useIngestJob } from "../hooks/useIngestJob";
import type { IngestKind } from "../types/api";

interface UploadPanelProps {
  kind: IngestKind;
  title: string;
  hint: string;
  accept: string;
}

export function UploadPanel({ kind, title, hint, accept }: UploadPanelProps) {
  const { runs, upload, dismiss } = useIngestJob(kind);
  const [label, setLabel] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (files: FileList | null) => {
    if (!files || !files.length) return;
    Array.from(files).forEach((f) => upload(f, label || undefined));
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="mb-3">
        <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-wide text-[var(--color-text)]">
          {title}
        </h3>
        <p className="mt-0.5 text-[11.5px] leading-snug text-[var(--color-text-muted)]">{hint}</p>
      </div>

      <input
        type="text"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Dataset label (optional)"
        className="mb-2.5 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2.5 py-1.5 text-[12px] text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] outline-none focus:border-[var(--color-accent)] transition-colors"
      />

      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed px-3 py-5 text-center transition-colors ${
          dragOver
            ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)]"
            : "border-[var(--color-border)] hover:border-[var(--color-text-faint)]"
        }`}
      >
        <UploadCloud size={18} className="text-[var(--color-text-muted)]" />
        <span className="text-[12px] text-[var(--color-text-muted)]">
          Drop a file or <span className="text-[var(--color-accent-strong)]">browse</span>
        </span>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </label>

      {runs.length > 0 && (
        <ul className="mt-3 flex flex-col gap-2">
          {runs.map((r) => (
            <li
              key={r.localId}
              className="fade-up rounded-lg border border-[var(--color-border-soft)] bg-[var(--color-surface-raised)] px-2.5 py-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex min-w-0 items-center gap-1.5">
                  <FileText size={13} className="shrink-0 text-[var(--color-text-faint)]" />
                  <span className="truncate text-[11.5px] font-medium text-[var(--color-text)]">
                    {r.fileName}
                  </span>
                </div>
                <button
                  onClick={() => dismiss(r.localId)}
                  aria-label="Dismiss"
                  className="shrink-0 rounded p-0.5 text-[var(--color-text-faint)] hover:bg-[var(--color-border)] hover:text-[var(--color-text)]"
                >
                  <X size={12} />
                </button>
              </div>
              <RunStatus run={r} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RunStatus({ run }: { run: ReturnType<typeof useIngestJob>["runs"][number] }) {
  if (run.error) {
    return (
      <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-[var(--color-danger)]">
        <AlertCircle size={12} />
        <span className="truncate">{run.error}</span>
      </div>
    );
  }
  if (!run.job) {
    return (
      <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
        <Loader2 size={12} className="animate-spin" />
        Starting…
      </div>
    );
  }

  const { status, current_step, progress_pct, rows_ingested, error } = run.job;

  if (status === "failed") {
    return (
      <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-[var(--color-danger)]">
        <AlertCircle size={12} />
        <span className="truncate">{error ?? "Ingestion failed"}</span>
      </div>
    );
  }

  if (status === "completed") {
    return (
      <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-[var(--color-success)]">
        <CheckCircle2 size={12} />
        {rows_ingested} {run.kind === "csv" ? "rows" : "chunks"} ingested
      </div>
    );
  }

  return (
    <div className="mt-1.5">
      <div className="mb-1 flex items-center justify-between text-[10.5px] text-[var(--color-text-muted)]">
        <span className="font-[family-name:var(--font-mono)]">{current_step}</span>
        <span>{Math.round(progress_pct)}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-border)]">
        <div
          className="h-full rounded-full bg-[var(--color-accent)] transition-[width] duration-300"
          style={{ width: `${Math.min(100, Math.max(2, progress_pct))}%` }}
        />
      </div>
    </div>
  );
}
