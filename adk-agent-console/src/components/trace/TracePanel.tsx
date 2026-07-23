import { AnimatePresence, motion } from 'framer-motion';
import { Radio, Waypoints } from 'lucide-react';
import TraceStep from './TraceStep';
import { routeColorClasses } from './RouteBadge';
import type { AgentTraceStep } from '@/types';

interface TracePanelProps {
  steps: AgentTraceStep[];
  isStreaming: boolean;
}

export default function TracePanel({ steps, isStreaming }: TracePanelProps) {
  const visibleSteps = steps.filter((s) => !s.isThrottle);
  const throttleTicks = steps.filter((s) => s.isThrottle);

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-hairline px-4">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Waypoints className="h-4 w-4 text-pulse" />
          Live Agent Trace
        </div>
        {isStreaming && (
          <span className="flex items-center gap-1.5 text-[11px] text-pulse">
            <Radio className="h-3 w-3 animate-pulse" />
            streaming
          </span>
        )}
      </div>

      <div className="scroll-thin flex-1 overflow-y-auto px-4 py-5">
        {visibleSteps.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center">
            <Waypoints className="h-6 w-6 text-zinc-700" />
            <p className="text-sm text-zinc-600">
              Send a message to watch the pipeline route, retrieve, and reason step by step.
            </p>
          </div>
        ) : (
          <div className="relative flex flex-col gap-3">
            {/* Signature element: a continuous spine running through every node.
                It recolors beneath a fork the moment the router picks a branch,
                visually encoding the SQL/VECTOR conditional in the backend graph. */}
            <Spine steps={visibleSteps} />
            <AnimatePresence initial={false}>
              {visibleSteps.map((step) => (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <TraceStep step={step} />
                </motion.div>
              ))}
            </AnimatePresence>

            {throttleTicks.length > 0 && (
              <div className="ml-9 flex items-center gap-1.5 pt-1">
                {throttleTicks.map((t) => (
                  <span
                    key={t.id}
                    title={`${t.agentName} (rate-limit throttle)`}
                    className="h-1 w-4 rounded-full bg-zinc-800"
                  />
                ))}
                <span className="ml-1 text-[10px] text-zinc-700">throttle steps</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Spine({ steps }: { steps: AgentTraceStep[] }) {
  // Build a stack of colored segments, one per gap between consecutive
  // steps, so the line's color reflects whichever route is active by that
  // point in the pipeline.
  let currentColor = '#2a2d38';

  return (
    <div className="pointer-events-none absolute bottom-3 left-2 top-3 flex w-px flex-col">
      {steps.map((step, i) => {
        if (step.route) {
          currentColor = routeHex(step.route);
        }
        if (i === steps.length - 1) return null;
        return <div key={step.id} className="w-px flex-1" style={{ background: currentColor }} />;
      })}
    </div>
  );
}

function routeHex(route: string): string {
  const c = routeColorClasses(route);
  if (c.text === 'text-sql') return '#e0a339';
  if (c.text === 'text-vector') return '#31b0a3';
  return '#3a3d4a';
}
