import { useCallback, useRef, useState } from 'react';
import { fetchIngestionStatus, uploadIngestionFile } from '@/lib/api/client';
import type { IngestionJob, IngestionKind, IngestionStatus, IngestionStatusResponseApi } from '@/types';

const POLL_INTERVAL_MS = 1000;

// IngestionStage's exact casing isn't visible from the routes alone, so this
// normalizes case-insensitively onto the four states the UI cares about.
function normalizeStatus(raw: string): IngestionStatus {
  const s = raw.toLowerCase();
  if (s.includes('fail') || s.includes('error')) return 'error';
  if (s.includes('complet') || s.includes('done')) return 'complete';
  if (s.includes('process') || s.includes('running')) return 'running';
  return 'queued';
}

function toJob(kind: IngestionKind, api: IngestionStatusResponseApi): IngestionJob {
  return {
    jobId: api.job_id,
    kind,
    fileName: api.file_name,
    status: normalizeStatus(api.status),
    progressPct: api.progress_pct,
    currentStep: api.current_step,
    rowsIngested: api.rows_ingested,
    error: api.error ?? undefined,
  };
}

export function useIngestion() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const pollers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const updateJob = useCallback((jobId: string, patch: Partial<IngestionJob>) => {
    setJobs((prev) => prev.map((j) => (j.jobId === jobId ? { ...j, ...patch } : j)));
  }, []);

  const stopPolling = useCallback((jobId: string) => {
    const handle = pollers.current[jobId];
    if (handle) {
      clearInterval(handle);
      delete pollers.current[jobId];
    }
  }, []);

  const pollJob = useCallback(
    (kind: IngestionKind, jobId: string) => {
      pollers.current[jobId] = setInterval(async () => {
        try {
          const api = await fetchIngestionStatus(kind, jobId);
          const job = toJob(kind, api);
          updateJob(jobId, job);
          if (job.status === 'complete' || job.status === 'error') {
            stopPolling(jobId);
          }
        } catch (err) {
          console.error('Ingestion status poll failed:', err);
          updateJob(jobId, { status: 'error', error: 'Lost connection while checking progress.' });
          stopPolling(jobId);
        }
      }, POLL_INTERVAL_MS);
    },
    [updateJob, stopPolling]
  );

  const upload = useCallback(
    async (kind: IngestionKind, file: File, datasetLabel?: string) => {
      try {
        const api = await uploadIngestionFile(kind, file, datasetLabel);
        const job = toJob(kind, api);
        setJobs((prev) => [...prev, job]);
        if (job.status !== 'complete' && job.status !== 'error') {
          pollJob(kind, job.jobId);
        }
      } catch (err) {
        console.error('Ingestion upload failed:', err);
        setJobs((prev) => [
          ...prev,
          {
            jobId: `failed-${Date.now()}`,
            kind,
            fileName: file.name,
            status: 'error',
            progressPct: 0,
            currentStep: 'upload_failed',
            error: err instanceof Error ? err.message : 'Upload failed.',
          },
        ]);
      }
    },
    [pollJob]
  );

  const dismissJob = useCallback(
    (jobId: string) => {
      stopPolling(jobId);
      setJobs((prev) => prev.filter((j) => j.jobId !== jobId));
    },
    [stopPolling]
  );

  return { jobs, upload, dismissJob };
}
