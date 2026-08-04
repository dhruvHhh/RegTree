import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listDocuments, uploadDocuments, getDocumentStatus } from "../api";
import type { DocumentSummary } from "../api";
import UploadZone from "./UploadZone";
import DocumentList from "./DocumentList";

const POLL_INTERVAL_MS = 3000;

export default function DocumentsPage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const refresh = useCallback(async () => {
    setDocuments(await listDocuments());
  }, []);

  useEffect(() => {
    refresh()
      .catch((e: unknown) => setUploadError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [refresh]);

  // Poll only while something is still processing; stops once nothing is.
  useEffect(() => {
    if (!documents.some((d) => d.status === "processing")) return;
    const timer = setTimeout(() => void refresh().catch(() => {}), POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [documents, refresh]);

  // Fetch the error message for any failed document we don't have one for yet.
  useEffect(() => {
    const missing = documents.filter((d) => d.status === "failed" && !(d.doc_id in errors));
    if (missing.length === 0) return;
    let cancelled = false;
    Promise.all(missing.map((d) => getDocumentStatus(d.doc_id).catch(() => null))).then((results) => {
      if (cancelled) return;
      const next: Record<string, string> = {};
      for (const r of results) {
        if (r?.error) next[r.doc_id] = r.error;
      }
      if (Object.keys(next).length > 0) setErrors((prev) => ({ ...prev, ...next }));
    });
    return () => {
      cancelled = true;
    };
  }, [documents, errors]);

  const handleUpload = useCallback(
    async (files: File[]) => {
      setUploadError(null);
      try {
        await uploadDocuments(files);
        await refresh();
      } catch (e: unknown) {
        setUploadError(e instanceof Error ? e.message : String(e));
      }
    },
    [refresh],
  );

  const query = filter.trim().toLowerCase();
  const filtered = query
    ? documents.filter((d) => d.filename.toLowerCase().includes(query))
    : documents;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold text-slate-100">Documents</h1>
          <p className="mt-1 text-sm text-slate-400">Manage the PDFs uploaded in this session.</p>
        </header>

        <UploadZone compact onUpload={handleUpload} />
        {uploadError && <p className="mt-3 text-sm text-red-400">{uploadError}</p>}

        <div className="mt-6 mb-3">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search by filename…"
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-white/30 focus:outline-none"
          />
        </div>

        <section className="rounded-xl border border-white/10 bg-[#0d0d0d]">
          {loading ? (
            <p className="px-4 py-10 text-center text-sm text-slate-500">Loading…</p>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center px-4 py-14 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-slate-500">
                <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                </svg>
              </div>
              <p className="text-sm font-medium text-slate-300">No documents yet</p>
              <p className="mt-1 text-sm text-slate-500">Upload a PDF above to get started.</p>
            </div>
          ) : filtered.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-slate-500">No documents match “{filter}”.</p>
          ) : (
            <DocumentList documents={filtered} errors={errors} onOpen={(id) => navigate(`/workspace/${id}`)} />
          )}
        </section>
      </div>
    </div>
  );
}
