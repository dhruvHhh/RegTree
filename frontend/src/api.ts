// Every backend call goes through request() so the session cookie is always sent.
// `/api` is same-origin: FastAPI serves the built app in production, and in dev Vite proxies
// it to localhost:8000 (see vite.config.ts).
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export type DocStatus = "processing" | "ready" | "failed" | "unknown";

export interface DocumentSummary {
  doc_id: string;
  filename: string;
  status: DocStatus;
}

export interface DocumentStatus {
  doc_id: string;
  status: DocStatus;
  error?: string;
}

export interface TreeNode {
  node_id?: string;
  title: string;
  summary?: string;
  start_page?: number;
  end_page?: number;
  children: TreeNode[];
}

export interface DocumentTree {
  doc_id: string;
  title: string;
  children: TreeNode[];
}

export interface Source {
  doc_id: string;
  node_id: string;
  title: string;
}

export interface QueryResult {
  answer: string;
  sources: Source[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include", ...init });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export function listDocuments(): Promise<DocumentSummary[]> {
  return request("/documents");
}

export function uploadDocuments(files: File[]): Promise<{ documents: DocumentSummary[] }> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return request("/documents", { method: "POST", body: form });
}

export function loadSampleDocuments(): Promise<{ documents: DocumentSummary[] }> {
  return request("/samples", { method: "POST" });
}

export function getDocumentStatus(docId: string): Promise<DocumentStatus> {
  return request(`/documents/${docId}/status`);
}

export function getDocumentTree(docId: string): Promise<DocumentTree> {
  return request(`/documents/${docId}/tree`);
}

export function askQuestion(question: string): Promise<QueryResult> {
  return request("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}
