// Single wrapper around the RegTree backend. Every backend call goes through
// here so the session cookie (credentials: "include") is never forgotten and
// raw fetch calls don't get scattered across components.

// Same-origin by default: requests hit the Vite dev server under `/api` and are
// proxied to the backend (see vite.config.ts), avoiding CORS/cookie issues.
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
