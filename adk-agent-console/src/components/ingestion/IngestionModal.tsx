import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, CheckCircle2, FileSpreadsheet, FileText, Loader2, Tag, X } from 'lucide-react';
import { useIngestion } from '@/hooks/useIngestion';
import UploadZone from './UploadZone';
import ProgressBar from './ProgressBar';
import { cn } from '@/lib/utils';

interface IngestionModalProps {
  open: boolean;
  onClose: () => void;
}

export default function IngestionModal({ open, onClose }: IngestionModalProps) {
  const { jobs, upload, dismissJob } = useIngestion();
  const [datasetLabel, setDatasetLabel] = useState('');

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg rounded-2xl border border-hairline bg-panel shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-hairline px-5 py-4">
              <h2 className="text-sm font-semibold text-zinc-100">Ingest data</h2>
              <button
                onClick={onClose}
                className="flex h-7 w-7 items-center justify-center rounded-md text-zinc-500 transition hover:bg-panel-raised hover:text-zinc-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-col gap-4 p-5">
              <label className="flex items-center gap-2 rounded-lg border border-hairline bg-panel-raised px-3 py-2">
                <Tag className="h-3.5 w-3.5 text-zinc-500" />
                <input
                  value={datasetLabel}
                  onChange={(e) => setDatasetLabel(e.target.value)}
                  placeholder="Dataset label (optional)"
                  className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none"
                />
              </label>

              <div className="grid grid-cols-2 gap-3">
                <UploadZone
                  label="Structured data"
                  hint="CSV, XLSX"
                  accept=".csv,.xlsx"
                  icon={<FileSpreadsheet className="h-4 w-4 text-sql" />}
                  accentClass="bg-sql/10"
                  onFile={(file) => upload('structured', file, datasetLabel || undefined)}
                />
                <UploadZone
                  label="Documents"
                  hint="PDF, MD, TXT"
                  accept=".pdf,.md,.txt"
                  icon={<FileText className="h-4 w-4 text-vector" />}
                  accentClass="bg-vector/10"
                  onFile={(file) => upload('document', file, datasetLabel || undefined)}
                />
              </div>

              {jobs.length > 0 && (
                <div className="flex flex-col gap-2 border-t border-hairline pt-4">
                  {jobs.map((job) => (
                    <JobRow key={job.jobId} job={job} onDismiss={() => dismissJob(job.jobId)} />
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function JobRow({ job, onDismiss }: { job: ReturnType<typeof useIngestion>['jobs'][number]; onDismiss: () => void }) {
  return (
    <div className="rounded-lg border border-hairline bg-panel-raised px-3 py-2.5">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="truncate text-xs font-medium text-zinc-300">{job.fileName}</span>
        <div className="flex shrink-0 items-center gap-1.5">
          <StatusIcon status={job.status} />
          {(job.status === 'complete' || job.status === 'error') && (
            <button onClick={onDismiss} className="text-zinc-600 hover:text-zinc-300">
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
      <ProgressBar pct={job.status === 'complete' ? 100 : job.progressPct} status={job.status} />
      <div className={cn('mt-1 text-[11px]', job.status === 'error' ? 'text-support' : 'text-zinc-500')}>
        {job.status === 'error'
          ? job.error ?? 'Ingestion failed.'
          : job.status === 'complete' && job.rowsIngested != null
            ? `Ingested ${job.rowsIngested.toLocaleString()} rows`
            : job.currentStep}
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'complete') return <CheckCircle2 className="h-3.5 w-3.5 text-success" />;
  if (status === 'error') return <AlertTriangle className="h-3.5 w-3.5 text-support" />;
  return <Loader2 className="h-3.5 w-3.5 animate-spin text-pulse" />;
}
