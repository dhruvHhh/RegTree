import { useEffect, useRef, useState } from "react";
import { ArrowUp, Plus } from "lucide-react";
import { askQuestion } from "../api";
import type { DocumentSummary, Source } from "../api";

interface Message {
  role: "user" | "assistant";
  text: string;
  sources?: Source[];
}

interface ChatPanelProps {
  onSourceClick: (source: Source) => void;
  // When both are provided (Home), the composer renders as a two-row card with a
  // "Select Documents" picker. Omitted elsewhere so the plain composer is unchanged.
  readyDocuments?: DocumentSummary[];
  onSelectDocument?: (docId: string) => void;
}

export default function ChatPanel({ onSourceClick, readyDocuments, onSelectDocument }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  async function send() {
    const question = input.trim();
    if (!question || thinking) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setThinking(true);
    try {
      const result = await askQuestion(question);
      setMessages((prev) => [...prev, { role: "assistant", text: result.answer, sources: result.sources }]);
    } catch (e: unknown) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Sorry, something went wrong: ${e instanceof Error ? e.message : String(e)}` },
      ]);
    } finally {
      setThinking(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && !thinking && (
          <p className="mt-8 text-center text-sm text-neutral-400">
            Ask a question about your documents to get started.
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={[
                "animate-fade-in max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                msg.role === "user"
                  ? "bg-brand text-white"
                  : "border border-slate-700 bg-slate-800 text-slate-100",
              ].join(" ")}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {msg.sources.map((s, j) => (
                    <button
                      key={j}
                      onClick={() => onSourceClick(s)}
                      title={`Go to section ${s.node_id}`}
                      className="rounded-full bg-slate-700 px-2 py-0.5 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white"
                    >
                      {s.node_id ? `${s.node_id} · ` : ""}
                      {s.title}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {thinking && (
          <div className="flex justify-start">
            <div className="animate-fade-in rounded-2xl border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm text-slate-400">
              Thinking…
            </div>
          </div>
        )}
      </div>

      {onSelectDocument ? (
        // Home: two-row composer card — input on top, actions below.
        <div className="p-3">
          <div className="rounded-2xl border border-white/10 bg-[#161616] p-2 shadow-lg">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              rows={1}
              placeholder="Ask a question…"
              className="max-h-32 w-full resize-none bg-transparent px-2 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
            />
            <div className="mt-1 flex items-center justify-between px-1">
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setPickerOpen((v) => !v)}
                  className="flex items-center gap-1 rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-slate-200 transition-colors hover:border-white/40 hover:text-white"
                >
                  <Plus size={14} />
                  Select Documents
                </button>
                {pickerOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setPickerOpen(false)} />
                    <div className="absolute bottom-full left-0 z-20 mb-2 max-h-60 w-64 overflow-y-auto rounded-xl border border-white/10 bg-[#141414] p-1 shadow-xl">
                      {(readyDocuments ?? []).length === 0 ? (
                        <p className="px-3 py-2 text-xs text-slate-500">No ready documents yet.</p>
                      ) : (
                        (readyDocuments ?? []).map((d) => (
                          <button
                            key={d.doc_id}
                            onClick={() => {
                              onSelectDocument(d.doc_id);
                              setPickerOpen(false);
                            }}
                            className="block w-full truncate rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-800"
                          >
                            {d.filename}
                          </button>
                        ))
                      )}
                    </div>
                  </>
                )}
              </div>
              <button
                type="button"
                onClick={() => void send()}
                disabled={thinking || input.trim() === ""}
                aria-label="Send"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-brand text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </div>
        </div>
      ) : (
        // Workspace: plain single-row composer.
        <div className="border-t border-slate-800 p-3">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              rows={1}
              placeholder="Ask a question…"
              className="max-h-32 flex-1 resize-none rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-white/30 focus:outline-none"
            />
            <button
              onClick={() => void send()}
              disabled={thinking || input.trim() === ""}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
