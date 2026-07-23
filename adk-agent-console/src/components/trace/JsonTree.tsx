import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

function isRecordArray(value: unknown): value is Record<string, unknown>[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((row) => typeof row === 'object' && row !== null && !Array.isArray(row))
  );
}

export function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  const preview = rows.slice(0, 25);

  return (
    <div className="overflow-hidden rounded-lg border border-hairline">
      <div className="scroll-thin max-h-64 overflow-auto">
        <table className="w-full border-collapse text-left text-[12px]">
          <thead className="sticky top-0 bg-panel-raised">
            <tr>
              {columns.map((col) => (
                <th key={col} className="whitespace-nowrap border-b border-hairline px-3 py-1.5 font-mono font-medium text-zinc-400">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.map((row, i) => (
              <tr key={i} className="odd:bg-panel/40">
                {columns.map((col) => (
                  <td key={col} className="whitespace-nowrap border-b border-hairline/60 px-3 py-1.5 font-mono text-zinc-300">
                    {String(row[col] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > preview.length && (
        <div className="border-t border-hairline bg-canvas px-3 py-1 text-[11px] text-zinc-600">
          Showing {preview.length} of {rows.length} rows
        </div>
      )}
    </div>
  );
}

/** Recursive, collapsible JSON viewer for anything that isn't a flat record table. */
export default function JsonTree({ data, depth = 0 }: { data: unknown; depth?: number }) {
  if (isRecordArray(data)) return <ResultTable rows={data} />;

  if (Array.isArray(data) || (typeof data === 'object' && data !== null)) {
    return <JsonNode data={data as object} depth={depth} defaultOpen={depth < 1} />;
  }

  return <span className="font-mono text-[12px] text-zinc-300">{JSON.stringify(data)}</span>;
}

function JsonNode({ data, depth, defaultOpen }: { data: object; depth: number; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const isArray = Array.isArray(data);
  const entries = Object.entries(data);

  if (entries.length === 0) {
    return <span className="font-mono text-[12px] text-zinc-600">{isArray ? '[]' : '{}'}</span>;
  }

  return (
    <div className="font-mono text-[12px]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-zinc-500 hover:text-zinc-300"
      >
        <ChevronRight className={cn('h-3 w-3 transition-transform', open && 'rotate-90')} />
        <span>
          {isArray ? '[' : '{'}
          {!open && `${entries.length} ${entries.length === 1 ? 'item' : 'items'}`}
          {!open && (isArray ? ']' : '}')}
        </span>
      </button>
      {open && (
        <div className="ml-3 border-l border-hairline pl-3">
          {entries.map(([key, value]) => (
            <div key={key} className="py-0.5">
              {!isArray && <span className="text-vector">{key}</span>}
              {!isArray && <span className="text-zinc-600">: </span>}
              <JsonTree data={value} depth={depth + 1} />
            </div>
          ))}
          <span className="text-zinc-500">{isArray ? ']' : '}'}</span>
        </div>
      )}
    </div>
  );
}
