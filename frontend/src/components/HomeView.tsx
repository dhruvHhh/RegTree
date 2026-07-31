import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listDocuments, uploadDocuments } from "../api";
import type { DocumentSummary, Source } from "../api";
import UploadZone from "./UploadZone";
import ChatPanel from "./ChatPanel";
import SideRays from "./effects/SideRays";

export default function HomeView() {
  const navigate = useNavigate();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [readyDocs, setReadyDocs] = useState<DocumentSummary[]>([]);

  // Ready documents for the composer's "Select Documents" picker.
  useEffect(() => {
    listDocuments()
      .then((docs) => setReadyDocs(docs.filter((d) => d.status === "ready")))
      .catch(() => {});
  }, []);

  // After uploading, hand off to the Documents page where status is polled.
  const handleUpload = useCallback(
    async (files: File[]) => {
      setUploadError(null);
      try {
        await uploadDocuments(files);
        navigate("/documents");
      } catch (e: unknown) {
        setUploadError(e instanceof Error ? e.message : String(e));
      }
    },
    [navigate],
  );

  // Home has no tree to scroll; open the cited document's workspace instead.
  function handleSourceClick(source: Source) {
    navigate(`/workspace/${source.doc_id}`);
  }

  return (
    <div className="relative h-full overflow-y-auto">
      {/* Ambient React Bits SideRays behind the content — non-interactive. */}
      <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden opacity-[0.65]">
        <SideRays rayColor1="#6bb4ff" rayColor2="#0A84FF" intensity={1.7} spread={1.45} opacity={0.7} />
      </div>

      <div className="relative z-10 mx-auto flex min-h-full max-w-2xl flex-col px-4 py-6 sm:py-10">
        <div className="mb-6 text-center sm:mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Turn dense documents into answers
          </h1>
          <p className="mt-3 text-sm text-slate-400 sm:text-base">
            Add your PDFs and RegTree maps their structure, so you can ask across all of them at once.
          </p>
        </div>

        <UploadZone onUpload={handleUpload} />
        {uploadError && <p className="mt-4 text-sm text-red-400">{uploadError}</p>}

        <div className="mt-6 flex min-h-[260px] flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0d0d0d] sm:mt-8 sm:min-h-[300px]">
          <ChatPanel
            onSourceClick={handleSourceClick}
            readyDocuments={readyDocs}
            onSelectDocument={(docId) => navigate(`/workspace/${docId}`)}
          />
        </div>
      </div>
    </div>
  );
}
