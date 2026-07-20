import { useCallback, useEffect, useRef, useState } from "react";
import { getIngestStatus, startIngest } from "../api/client";
import type { IngestJob, IngestKind } from "../types/api";

const POLL_INTERVAL_MS = 1000;

export interface IngestRun {
  localId: string;
  kind: IngestKind;
  fileName: string;
  datasetLabel?: string;
  job: IngestJob | null;
  error: string | null;
}

export function useIngestJob(kind: IngestKind) {
  const [runs, setRuns] = useState<IngestRun[]>([]);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    return () => {
      Object.values(timers.current).forEach(clearTimeout);
    };
  }, []);

  const poll = useCallback(
    (localId: string, jobId: string) => {
      const tick = async () => {
        try {
          const job = await getIngestStatus(kind, jobId);
          setRuns((prev) =>
            prev.map((r) => (r.localId === localId ? { ...r, job, error: null } : r))
          );
          if (job.status === "processing" || job.status === "idle") {
            timers.current[localId] = setTimeout(tick, POLL_INTERVAL_MS);
          }
        } catch (err) {
          setRuns((prev) =>
            prev.map((r) =>
              r.localId === localId
                ? { ...r, error: (err as Error).message ?? "Polling failed" }
                : r
            )
          );
          timers.current[localId] = setTimeout(tick, POLL_INTERVAL_MS * 2);
        }
      };
      tick();
    },
    [kind]
  );

  const upload = useCallback(
    async (file: File, datasetLabel?: string) => {
      const localId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const run: IngestRun = {
        localId,
        kind,
        fileName: file.name,
        datasetLabel,
        job: null,
        error: null,
      };
      setRuns((prev) => [run, ...prev]);
      try {
        const job = await startIngest(kind, file, datasetLabel);
        setRuns((prev) =>
          prev.map((r) => (r.localId === localId ? { ...r, job } : r))
        );
        poll(localId, job.job_id);
      } catch (err) {
        setRuns((prev) =>
          prev.map((r) =>
            r.localId === localId
              ? { ...r, error: (err as Error).message ?? "Upload failed" }
              : r
          )
        );
      }
    },
    [kind, poll]
  );

  const dismiss = useCallback((localId: string) => {
    clearTimeout(timers.current[localId]);
    delete timers.current[localId];
    setRuns((prev) => prev.filter((r) => r.localId !== localId));
  }, []);

  return { runs, upload, dismiss };
}
