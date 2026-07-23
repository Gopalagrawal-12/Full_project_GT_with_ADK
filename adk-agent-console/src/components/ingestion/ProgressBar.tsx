import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import type { IngestionStatus } from '@/types';

export default function ProgressBar({ pct, status }: { pct: number; status: IngestionStatus }) {
  const color =
    status === 'error' ? 'bg-support' : status === 'complete' ? 'bg-success' : 'bg-pulse';

  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-panel-raised">
      <motion.div
        className={cn('h-full rounded-full', color)}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      />
    </div>
  );
}
