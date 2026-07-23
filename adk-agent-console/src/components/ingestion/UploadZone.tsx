import { useRef, useState } from 'react';
import { UploadCloud } from 'lucide-react';
import { cn } from '@/lib/utils';

interface UploadZoneProps {
  label: string;
  hint: string;
  accept: string;
  icon: React.ReactNode;
  accentClass: string;
  onFile: (file: File) => void;
}

export default function UploadZone({ label, hint, accept, icon, accentClass, onFile }: UploadZoneProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      onClick={() => inputRef.current?.click()}
      className={cn(
        'flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center transition',
        dragging ? cn('border-pulse bg-pulse/5') : 'border-hairline hover:border-zinc-700 hover:bg-panel-raised/60'
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = '';
        }}
      />
      <div className={cn('flex h-9 w-9 items-center justify-center rounded-lg', accentClass)}>{icon}</div>
      <div className="text-sm font-medium text-zinc-200">{label}</div>
      <div className="text-xs text-zinc-500">{hint}</div>
      <div className="mt-1 flex items-center gap-1 text-[11px] text-zinc-600">
        <UploadCloud className="h-3 w-3" />
        Drop file or click to browse
      </div>
    </div>
  );
}
