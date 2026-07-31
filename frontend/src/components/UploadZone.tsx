import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { FileStack, Upload } from "lucide-react";

interface UploadZoneProps {
  onUpload: (files: File[]) => Promise<void>;
  disabled?: boolean;
  compact?: boolean;
}

export default function UploadZone({ onUpload, disabled, compact }: UploadZoneProps) {
  const [busy, setBusy] = useState(false);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      if (accepted.length === 0) return;
      setBusy(true);
      try {
        await onUpload(accepted);
      } finally {
        setBusy(false);
      }
    },
    [onUpload],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    disabled: disabled || busy,
  });

  const active = isDragActive && !disabled && !busy;
  const box = [
    "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed text-center transition-colors",
    active ? "border-white/50 bg-white/[0.04]" : "border-white/15 bg-[#0d0d0d] hover:border-white/30 hover:bg-[#141414]",
    disabled || busy ? "cursor-not-allowed opacity-60" : "",
  ];

  // Compact variant (Documents page): a small, unobtrusive dropzone.
  if (compact) {
    return (
      <div {...getRootProps()} className={[...box, "px-6 py-8"].join(" ")}>
        <input {...getInputProps()} />
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-slate-200">
          <Upload size={20} />
        </div>
        <p className="text-sm font-medium text-slate-200">
          {busy ? "Reading your files…" : "Drop your PDFs here, or click to browse"}
        </p>
      </div>
    );
  }

  // Full variant (Home): large focal dropzone with an explicit Upload button.
  return (
    <div {...getRootProps()} className={[...box, "px-6 py-10 sm:px-8 sm:py-12"].join(" ")}>
      <input {...getInputProps()} />
      <FileStack size={56} strokeWidth={1.5} className="mb-5 text-slate-100" />
      <h3 className="text-lg font-bold text-slate-100">{busy ? "Reading your files…" : "Drop your PDFs here"}</h3>
      <p className="mt-2 text-sm text-slate-500">Drag &amp; drop PDFs, or click to browse your files</p>
      <button
        type="button"
        onClick={(e) => {
          // The whole box already opens the picker on click; stop propagation so
          // this explicit button doesn't open it a second time.
          e.stopPropagation();
          open();
        }}
        disabled={disabled || busy}
        className="mt-6 inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Upload size={16} />
        Upload
      </button>
    </div>
  );
}
