import { GitFork } from 'lucide-react';
import { cn } from '@/lib/utils';

export function routeColorClasses(route: string) {
  const r = route.toLowerCase();
  if (r.includes('sql')) {
    return { text: 'text-sql', bg: 'bg-sql/10', border: 'border-sql/30', dot: 'bg-sql' };
  }
  if (r.includes('vector')) {
    return { text: 'text-vector', bg: 'bg-vector/10', border: 'border-vector/30', dot: 'bg-vector' };
  }
  return { text: 'text-zinc-400', bg: 'bg-zinc-800/50', border: 'border-zinc-700', dot: 'bg-zinc-500' };
}

export default function RouteBadge({ route }: { route: string }) {
  const c = routeColorClasses(route);
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-wide',
        c.text,
        c.bg,
        c.border
      )}
    >
      <GitFork className="h-3 w-3" />
      {route} branch
    </span>
  );
}
