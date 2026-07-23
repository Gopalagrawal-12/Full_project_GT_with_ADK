import { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Check, Copy } from 'lucide-react';

export default function SqlBlock({ label, sql }: { label: string; sql: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="overflow-hidden rounded-lg border border-hairline">
      <div className="flex items-center justify-between border-b border-hairline bg-canvas px-3 py-1.5">
        <span className="font-mono text-[11px] uppercase tracking-wide text-sql">{label}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1 text-[11px] text-zinc-500 transition hover:text-zinc-200"
        >
          {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        language="sql"
        style={vscDarkPlus}
        customStyle={{
          margin: 0,
          padding: '12px 14px',
          background: '#0a0b0f',
          fontSize: '12.5px',
          lineHeight: 1.6,
        }}
        wrapLongLines
      >
        {sql}
      </SyntaxHighlighter>
    </div>
  );
}
