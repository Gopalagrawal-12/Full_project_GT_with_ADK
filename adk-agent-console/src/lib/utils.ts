import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getOrCreateUserId(): string {
  const key = 'adk_console_user_id';
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

export function shortId(): string {
  return Math.random().toString(36).slice(2, 10);
}

// Agent names arrive as "pipeline/sql_generator" — the trace UI only wants
// the leaf name; the raw name is kept around for the throttle-node filter.
export function agentLeafName(agent: string): string {
  const parts = agent.split('/');
  return parts[parts.length - 1] || agent;
}

export function isThrottleAgent(agent: string): boolean {
  const leaf = agentLeafName(agent).toLowerCase();
  return leaf.startsWith('delay_') || leaf.startsWith('vector_delay_');
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}
