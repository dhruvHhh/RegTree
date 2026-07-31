import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { getDocumentTree, listDocuments } from "../api";
import type { DocumentSummary, DocumentTree, Source } from "../api";
import TreeView, { treeNodeDomId } from "./TreeView";
import ChatPanel from "./ChatPanel";

export default function Workspace() {
  const { docId } = useParams<{ docId: string }>();
  const navigate = useNavigate();
  const [tree, setTree] = useState<DocumentTree | null>(null);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [readyDocs, setReadyDocs] = useState<DocumentSummary[]>([]);
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null);

  // Load the tree whenever the selected document changes.
  useEffect(() => {
    if (!docId) return;
    setTree(null);
    setTreeError(null);
    getDocumentTree(docId)
      .then(setTree)
      .catch((e: unknown) => setTreeError(e instanceof Error ? e.message : String(e)));
  }, [docId]);

  // Ready documents for the switcher.
  useEffect(() => {
    listDocuments()
      .then((docs) => setReadyDocs(docs.filter((d) => d.status === "ready")))
      .catch(() => {});
  }, [docId]);

  // Scroll to and briefly highlight a cited node once its tree is loaded.
  useEffect(() => {
    if (!highlightNodeId || !tree) return;
    const el = document.getElementById(treeNodeDomId(highlightNodeId));
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    const timer = setTimeout(() => setHighlightNodeId(null), 2500);
    return () => clearTimeout(timer);
  }, [highlightNodeId, tree]);

  function handleSourceClick(source: Source) {
    setHighlightNodeId(source.node_id);
    // A source can belong to another document in the same session; jump there first.
    if (source.doc_id !== docId) navigate(`/workspace/${source.doc_id}`);
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-4 border-b border-slate-800 bg-[#0b0f17] px-4 py-3">
        <Link to="/documents" className="text-sm font-medium text-slate-300 hover:text-white">
          ← Documents
        </Link>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">Document</span>
          <select
            value={docId}
            onChange={(e) => navigate(`/workspace/${e.target.value}`)}
            className="rounded-lg border border-slate-700 bg-slate-800 px-2 py-1 text-sm text-slate-100 focus:border-white/30 focus:outline-none"
          >
            {/* Ensure the current doc appears even before the list resolves. */}
            {readyDocs.every((d) => d.doc_id !== docId) && docId && (
              <option value={docId}>Current document</option>
            )}
            {readyDocs.map((d) => (
              <option key={d.doc_id} value={d.doc_id}>
                {d.filename}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <aside className="min-h-0 overflow-y-auto border-r border-slate-800 bg-slate-900/40 p-4">
          {treeError ? (
            <p className="text-sm text-red-400">Could not load document structure: {treeError}</p>
          ) : !tree ? (
            <p className="text-sm text-slate-500">Loading structure…</p>
          ) : (
            <TreeView tree={tree} highlightNodeId={highlightNodeId} />
          )}
        </aside>

        <main className="min-h-0 bg-[#050505]">
          <ChatPanel onSourceClick={handleSourceClick} />
        </main>
      </div>
    </div>
  );
}
