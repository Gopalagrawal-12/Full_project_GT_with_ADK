import { useState } from "react";
import { ChevronDown, ChevronRight, GitBranch } from "lucide-react";
import type { TraceStep } from "../types/api";

function nodeColor(node: string): string {
  const n = node.toLowerCase();
  if (n.includes("classif") || n.includes("rout")) return "var(--color-node-classify)";
  if (n.includes("sql") || n.includes("vector") || n.includes("retriev") || n.includes("search"))
    return "var(--color-node-retrieve)";
  if (n.includes("synth") || n.includes("generat") || n.includes("answer"))
    return "var(--color-node-generate)";
  if (n.includes("support") || n.includes("fallback")) return "var(--color-node-support)";
  if (n.includes("error")) return "var(--color-node-error)";
  return "var(--color-text-faint)";
}

function humanize(node: string): string {
  return node.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function TracePanel({ trace, routedTo }: { trace: TraceStep[]; routedTo?: string | null }) {
  if (!trace.length) return null;

  return (
    <div className="mt-2 rounded-lg border border-[var(--color-border-soft)] bg-[var(--color-surface)]">
      <div className="flex items-center gap-1.5 border-b border-[var(--color-border-soft)] px-3 py-2">
        <GitBranch size={12} className="text-[var(--color-text-faint)]" />
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] uppercase tracking-wider text-[var(--color-text-faint)]">
          Agent trace
        </span>
        {routedTo && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{
              color: nodeColor(routedTo),
              background: `color-mix(in srgb, ${nodeColor(routedTo)} 16%, transparent)`,
            }}
          >
            → {humanize(routedTo)}
          </span>
        )}
      </div>

      <ol className="flex flex-col px-3 py-2.5">
        {trace.map((step, i) => (
          <TraceRow key={i} step={step} isLast={i === trace.length - 1} />
        ))}
      </ol>
    </div>
  );
}

function TraceRow({ step, isLast }: { step: TraceStep; isLast: boolean }) {
  const [open, setOpen] = useState(false);
  const color = nodeColor(step.node);
  const hasDelta = step.state_delta && Object.keys(step.state_delta).length > 0;

  return (
    <li className="relative flex gap-2.5 pb-2.5 last:pb-0">
      {!isLast && (
        <span
          className="absolute left-[5px] top-3 bottom-0 w-px"
          style={{ background: "var(--color-border)" }}
        />
      )}
      <span
        className="relative mt-1 h-[11px] w-[11px] shrink-0 rounded-full border-2"
        style={{ borderColor: color, background: "var(--color-surface)" }}
      />
      <div className="min-w-0 flex-1">
        <button
          onClick={() => hasDelta && setOpen((v) => !v)}
          disabled={!hasDelta}
          className="flex w-full items-center gap-1.5 text-left disabled:cursor-default"
        >
          <span className="text-[12px] font-medium" style={{ color }}>
            {humanize(step.node)}
          </span>
          {step.status === "error" && (
            <span className="text-[10px] font-medium text-[var(--color-danger)]">failed</span>
          )}
          {typeof step.duration_ms === "number" && (
            <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--color-text-faint)]">
              {step.duration_ms}ms
            </span>
          )}
          {hasDelta &&
            (open ? (
              <ChevronDown size={12} className="ml-auto text-[var(--color-text-faint)]" />
            ) : (
              <ChevronRight size={12} className="ml-auto text-[var(--color-text-faint)]" />
            ))}
        </button>
        {hasDelta && open && (
          <pre className="fade-up mt-1.5 max-h-56 overflow-auto rounded-md border border-[var(--color-border-soft)] bg-[var(--color-bg)] p-2 font-[family-name:var(--font-mono)] text-[10.5px] leading-relaxed text-[var(--color-text-muted)]">
            {JSON.stringify(step.state_delta, null, 2)}
          </pre>
        )}
      </div>
    </li>
  );
}
