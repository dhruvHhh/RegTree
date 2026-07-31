import { FileText } from "lucide-react";
import type { DocumentSummary, DocStatus } from "../api";

interface DocumentListProps {
  documents: DocumentSummary[];
  errors: Record<string, string>; // doc_id -> error message, for failed docs
  onOpen: (docId: string) => void;
}

const BADGE: Record<DocStatus, { label: string; dot: string; text: string; bg: string }> = {
  processing: { label: "Processing", dot: "bg-amber-400", text: "text-amber-300", bg: "bg-amber-400/10" },
  ready: { label: "Ready", dot: "bg-emerald-400", text: "text-emerald-300", bg: "bg-emerald-400/10" },
  failed: { label: "Failed", dot: "bg-red-400", text: "text-red-300", bg: "bg-red-400/10" },
  unknown: { label: "Unknown", dot: "bg-slate-400", text: "text-slate-300", bg: "bg-slate-400/10" },
};

function StatusBadge({ status }: { status: DocStatus }) {
  const b = BADGE[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${b.bg} ${b.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${b.dot} ${status === "processing" ? "animate-pulse" : ""}`} />
      {b.label}
    </span>
  );
}

export default function DocumentList({ documents, errors, onOpen }: DocumentListProps) {
  return (
    <ul className="divide-y divide-white/5">
      {documents.map((doc) => {
        const ready = doc.status === "ready";
        const error = doc.status === "failed" ? errors[doc.doc_id] : undefined;
        return (
          <li
            key={doc.doc_id}
            onClick={() => ready && onOpen(doc.doc_id)}
            title={error}
            className={[
              "animate-fade-in group flex items-center justify-between gap-4 px-4 py-3.5 transition-colors",
              ready ? "cursor-pointer hover:bg-white/5" : "cursor-default",
            ].join(" ")}
          >
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/5 text-slate-400">
                <FileText size={17} />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-100">{doc.filename}</p>
                {error ? (
                  <p className="truncate text-xs text-red-400">{error}</p>
                ) : (
                  <p className="truncate text-xs text-slate-500">
                    {doc.status === "processing" ? "Extracting text and building structure…" : "PDF document"}
                  </p>
                )}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <StatusBadge status={doc.status} />
              {ready && (
                <span className="text-xs text-slate-500 transition-colors group-hover:text-slate-200">Open →</span>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
