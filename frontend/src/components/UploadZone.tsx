import { useCallback, useImperativeHandle, useState } from "react";
import type { Ref } from "react";
import { useDropzone } from "react-dropzone";
import { Upload } from "lucide-react";

export interface UploadZoneHandle {
  open: () => void;
}

interface UploadZoneProps {
  onUpload: (files: File[]) => Promise<void>;
  disabled?: boolean;
  // Lets a button outside the dropzone (the Home hero) open the file picker.
  ref?: Ref<UploadZoneHandle>;
}

export default function UploadZone({ onUpload, disabled, ref }: UploadZoneProps) {
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

  // react-dropzone hands back a null `open` while disabled, so guard the call.
  useImperativeHandle(ref, () => ({ open: () => open?.() }), [open]);

  const active = isDragActive && !disabled && !busy;
  const box = [
    "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-colors",
    active ? "border-white/50 bg-white/[0.04]" : "border-white/15 bg-[#0d0d0d] hover:border-white/30 hover:bg-[#141414]",
    disabled || busy ? "cursor-not-allowed opacity-60" : "",
  ];

  return (
    <div {...getRootProps()} className={box.join(" ")}>
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
