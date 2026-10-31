import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileSearch, FileText, Info, ListTree, Upload } from "lucide-react";
import { listDocuments, loadSampleDocuments, uploadDocuments, uploadErrorMessage } from "../api";
import type { DocumentSummary, Source } from "../api";
import UploadZone from "./UploadZone";
import type { UploadZoneHandle } from "./UploadZone";
import ChatPanel from "./ChatPanel";
import { Spotlight } from "@/components/ui/spotlight";
import { BentoGrid, BentoGridItem } from "@/components/ui/bento-grid";

export default function HomeView() {
  const navigate = useNavigate();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [readyDocs, setReadyDocs] = useState<DocumentSummary[]>([]);
  const [loadingSamples, setLoadingSamples] = useState(false);
  const uploadZoneRef = useRef<UploadZoneHandle>(null);
  const howItWorksRef = useRef<HTMLElement>(null);

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
      } catch (err) {
        setUploadError(uploadErrorMessage(err));
      }
    },
    [navigate],
  );

  async function handleTrySamples() {
    setUploadError(null);
    setLoadingSamples(true);
    try {
      await loadSampleDocuments();
      navigate("/documents");
    } catch {
      setUploadError("Couldn't load the sample documents — please try again.");
      setLoadingSamples(false);
    }
  }

  // Home has no tree to scroll; open the cited document's workspace instead.
  function handleSourceClick(source: Source) {
    navigate(`/workspace/${source.doc_id}`);
  }

  return (
    <div className="relative h-full overflow-y-auto">
      <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden opacity-60">
        <Spotlight className="-top-40 left-0 md:-top-20 md:left-40" fill="white" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-full max-w-2xl flex-col px-4 py-6 sm:py-10">
        <section className="mb-8 sm:mb-10">
          <h1 className="text-3xl leading-[1.2] font-medium tracking-tight text-slate-100 sm:text-5xl">
            <span className="block">Ask smarter.</span>
            <span className="block">
              <span className="underline decoration-brand decoration-3 underline-offset-8">Cite</span> everything.
            </span>
          </h1>
          <p className="mt-4 max-w-xl text-sm text-slate-400 sm:text-base">
            Upload regulatory PDFs, ask questions in plain English, and get answers that point to the exact section
            they came from.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
            <button
              type="button"
              onClick={() => uploadZoneRef.current?.open()}
              className="inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-medium text-white transition hover:brightness-110"
            >
              <Upload size={16} />
              Upload a document
            </button>
            <button
              type="button"
              onClick={() => void handleTrySamples()}
              disabled={loadingSamples}
              className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-5 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:border-white/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <FileText size={16} />
              Try sample documents
            </button>
            <button
              type="button"
              onClick={() => howItWorksRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
              className="text-sm font-medium text-slate-300 transition-colors hover:text-white"
            >
              How it works →
            </button>
          </div>
        </section>

        <UploadZone ref={uploadZoneRef} onUpload={handleUpload} />
        {uploadError && <p className="mt-3 text-sm text-red-400">{uploadError}</p>}
        <p className="mt-3 flex items-start gap-1.5 text-xs text-slate-500">
          <Info size={14} className="mt-px shrink-0" />
          Documents are only visible in this browser session — no account, and nothing is kept long-term.
        </p>

        <div className="mt-6 flex min-h-[260px] flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0d0d0d] sm:mt-8 sm:min-h-[300px]">
          <ChatPanel
            onSourceClick={handleSourceClick}
            readyDocuments={readyDocs}
            onSelectDocument={(docId) => navigate(`/workspace/${docId}`)}
          />
        </div>
      </div>

      <section ref={howItWorksRef} className="relative z-10 mx-auto max-w-2xl px-4 pb-16">
        <div className="border-t border-white/10 pt-10">
          <h2 className="text-2xl font-bold tracking-tight text-white">How it works</h2>
          {/* Override Bento's fixed 18rem rows so the cards size to their copy. */}
          <BentoGrid className="mt-6 md:auto-rows-auto md:grid-cols-2">
            <BentoGridItem
              icon={<FileSearch size={20} className="text-slate-400" />}
              title="What it does"
              description={
                <p className="text-sm leading-relaxed">
                  Upload regulatory PDFs — circulars, policies, guidelines — and ask questions about them in plain
                  English. RegTree looks across every document you've added and shows the exact sections each answer
                  came from, so you can jump straight to them.
                </p>
              }
            />
            <BentoGridItem
              icon={<ListTree size={20} className="text-slate-400" />}
              title="Why the answers hold up"
              description={
                <p className="text-sm leading-relaxed">
                  When you upload a document, RegTree reads it and builds an outline of its chapters and sections,
                  much like a detailed table of contents. When you ask a question, it works through that outline to
                  find the part that actually covers your topic, instead of guessing from passages that happen to use
                  similar words.
                </p>
              }
            />
          </BentoGrid>
        </div>
      </section>
    </div>
  );
}
