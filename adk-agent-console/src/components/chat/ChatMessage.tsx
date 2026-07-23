import ReactMarkdown from 'react-markdown';
import { Clock3, LifeBuoy, Rows3, User, Workflow } from 'lucide-react';
import { cn } from '@/lib/utils';
import { routeColorClasses } from '@/components/trace/RouteBadge';
import type { ChatMessage as ChatMessageType } from '@/types';

export default function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === 'user';
  const summary = message.summary;
  const hasSummary =
    summary && (summary.queryPath || summary.rowCount != null || summary.elapsedMs != null);

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-zinc-800 text-zinc-400' : 'bg-pulse/15 text-pulse'
        )}
      >
        {isUser ? <User className="h-3.5 w-3.5" /> : <Workflow className="h-3.5 w-3.5" />}
      </div>

      <div className={cn('flex max-w-[85%] flex-col gap-1.5', isUser && 'items-end')}>
        {message.isSupportFallback && (
          <span className="flex items-center gap-1 rounded-full border border-support/30 bg-support/10 px-2 py-0.5 text-[11px] text-support">
            <LifeBuoy className="h-3 w-3" />
            Support agent · no matching data found
          </span>
        )}

        <div
          className={cn(
            'rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
            isUser
              ? 'rounded-tr-sm bg-pulse/15 text-zinc-100'
              : 'rounded-tl-sm border border-hairline bg-panel-raised text-zinc-200'
          )}
        >
          {message.pending && !message.content ? (
            <span className="shimmer-text">Thinking…</span>
          ) : isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-pre:bg-canvas prose-pre:border prose-pre:border-hairline prose-code:text-pulse prose-headings:text-zinc-100">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && hasSummary && (
          <div className="flex flex-wrap items-center gap-2 px-1 text-[11px] text-zinc-600">
            {summary!.queryPath && (
              <span className={cn('font-mono', routeColorClasses(summary!.queryPath).text)}>
                {summary!.queryPath}
              </span>
            )}
            {summary!.rowCount != null && (
              <span className="flex items-center gap-1">
                <Rows3 className="h-3 w-3" />
                {summary!.rowCount.toLocaleString()} rows
              </span>
            )}
            {summary!.elapsedMs != null && (
              <span className="flex items-center gap-1">
                <Clock3 className="h-3 w-3" />
                {summary!.elapsedMs < 1000 ? `${Math.round(summary!.elapsedMs)}ms` : `${(summary!.elapsedMs / 1000).toFixed(1)}s`}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
