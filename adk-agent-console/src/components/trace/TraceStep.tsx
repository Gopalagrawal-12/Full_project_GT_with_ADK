import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle2, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AgentTraceStep } from '@/types';
import RouteBadge, { routeColorClasses } from './RouteBadge';
import SqlBlock from './SqlBlock';
import JsonTree from './JsonTree';

const SQL_KEYS = ['generated_sql', 'reviewed_sql'];
const RESULT_KEYS = ['execution_result'];
const SKIP_KEYS = ['route', ...SQL_KEYS, ...RESULT_KEYS];

export default function TraceStep({ step }: { step: AgentTraceStep }) {
  const [open, setOpen] = useState(step.status === 'active');
  const deltaKeys = Object.keys(step.delta);
  const hasPayload = deltaKeys.length > 0;
  const glow = step.route ? routeColorClasses(step.route) : null;

  return (
    <div className="relative pl-9">
      <StatusDot status={step.status} route={step.route} />

      <button
        onClick={() => hasPayload && setOpen((v) => !v)}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition',
          step.status === 'active'
            ? 'border-pulse-dim bg-pulse/[0.06] shadow-glow'
            : 'border-hairline bg-panel-raised hover:border-zinc-700'
        )}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-[13px] text-zinc-200">{step.agentName}</span>
          {step.route && (
            <span className={cn('h-1.5 w-1.5 rounded-full', glow?.dot)} title={`${step.route} route`} />
          )}
        </div>
        {hasPayload && (
          <ChevronDown className={cn('h-3.5 w-3.5 text-zinc-500 transition-transform', open && 'rotate-180')} />
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && hasPayload && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="mt-2 flex flex-col gap-2.5 pb-1">
              {step.route && <RouteBadge route={step.route} />}

              {SQL_KEYS.filter((k) => step.delta[k]).map((k) => (
                <SqlBlock key={k} label={k.replace('_', ' ')} sql={String(step.delta[k])} />
              ))}

              {RESULT_KEYS.filter((k) => step.delta[k] !== undefined).map((k) => (
                <div key={k}>
                  <div className="mb-1 font-mono text-[11px] uppercase tracking-wide text-zinc-500">{k}</div>
                  <JsonTree data={step.delta[k]} />
                </div>
              ))}

              {deltaKeys
                .filter((k) => !SKIP_KEYS.includes(k))
                .map((k) => (
                  <div key={k}>
                    <div className="mb-1 font-mono text-[11px] uppercase tracking-wide text-zinc-500">{k}</div>
                    <JsonTree data={step.delta[k]} />
                  </div>
                ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StatusDot({ status, route }: { status: AgentTraceStep['status']; route?: string | null }) {
  const c = route ? routeColorClasses(route) : null;

  return (
    <span className="absolute left-0 top-2 flex h-4 w-4 items-center justify-center">
      {status === 'active' ? (
        <>
          <span className="absolute h-3 w-3 rounded-full bg-pulse animate-pulse-ring" />
          <span className="relative h-2 w-2 rounded-full bg-pulse" />
        </>
      ) : (
        <CheckCircle2 className={cn('h-4 w-4', c ? c.text : 'text-success')} strokeWidth={2.5} />
      )}
    </span>
  );
}
