"""MCP server exposing RegTree's pipeline as tools for Claude Desktop (stdio)."""

import sys
import os

# Claude Desktop launches this from another cwd, and Spark workers inherit env vars but
# not sys.path, so the backend dir goes on PYTHONPATH too. Must run before pyspark is imported.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

existing = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = BACKEND_DIR + (os.pathsep + existing if existing else "")

import time
import uuid
from contextlib import redirect_stdout

from fastmcp import FastMCP

import storage
from ingest.spark_job import extract_text_parallel
from rag.pageindex_builder import build_tree
from rag.retrieval import answer_question

# MCP clients carry no cookies, so this server keeps one persistent session, separate from web ones.
_SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mcp_session_id")


def _mcp_session_id() -> str:
    """Return this server's fixed local session id, creating it once if missing."""
    if os.path.exists(_SESSION_FILE):
        with open(_SESSION_FILE, "r", encoding="utf-8") as f:
            sid = f.read().strip()
        if sid:
            return sid
    sid = str(uuid.uuid4())
    with open(_SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(sid)
    return sid


SESSION_ID = _mcp_session_id()

mcp = FastMCP("regtree")


def _log(msg: str) -> None:
    """Timestamped line to stderr — shows up in Claude Desktop's MCP logs."""
    print(f"[mcp {time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


@mcp.tool
def upload_document(file_path: str) -> dict:
    """
    Upload a local PDF into RegTree and process it end to end.

    Reads the file at `file_path`, stores it under the MCP session, extracts its
    text and builds its section tree (synchronously — a few seconds is fine for a
    single tool call). Returns {"doc_id", "status"} where status is "ready", or
    "failed" with an "error" message.
    """
    if not os.path.isfile(file_path):
        return {"status": "failed", "error": f"File not found: {file_path}"}

    doc_id = str(uuid.uuid4())
    filename = os.path.basename(file_path)

    raw_dir = storage.raw_pdfs_dir(SESSION_ID)
    os.makedirs(raw_dir, exist_ok=True)
    pdf_path = os.path.join(raw_dir, f"{doc_id}.pdf")
    with open(file_path, "rb") as src, open(pdf_path, "wb") as dst:
        dst.write(src.read())

    storage.record_document(SESSION_ID, doc_id, filename)

    # stdout is MCP's JSON-RPC channel, so the pipeline's progress prints go to stderr.
    # Returns stay outside this block so the tool's response is never redirected.
    build_error = None
    with redirect_stdout(sys.stderr):
        _log(f"extract: start ({filename})")
        t0 = time.monotonic()
        errors = extract_text_parallel(SESSION_ID, [{"doc_id": doc_id, "pdf_path": pdf_path}])
        _log(f"extract: done in {time.monotonic() - t0:.1f}s")
        if doc_id not in errors:
            _log("build_tree: start")
            t1 = time.monotonic()
            try:
                build_tree(SESSION_ID, doc_id)
                _log(f"build_tree: done in {time.monotonic() - t1:.1f}s")
            except Exception as exc:
                build_error = str(exc)
                _log(f"build_tree: FAILED after {time.monotonic() - t1:.1f}s: {exc}")

    if doc_id in errors:
        storage.set_document_status(SESSION_ID, doc_id, "failed", errors[doc_id])
        return {"doc_id": doc_id, "status": "failed", "error": errors[doc_id]}
    if build_error is not None:
        storage.set_document_status(SESSION_ID, doc_id, "failed", build_error)
        return {"doc_id": doc_id, "status": "failed", "error": build_error}

    storage.set_document_status(SESSION_ID, doc_id, "ready")
    return {"doc_id": doc_id, "status": "ready"}


@mcp.tool
def list_documents() -> list[dict]:
    """List the documents uploaded via this MCP session (doc_id, filename, status)."""
    return [
        {"doc_id": d["doc_id"], "filename": d["filename"], "status": d.get("status", "unknown")}
        for d in storage.load_manifest(SESSION_ID)
    ]


@mcp.tool
def query_documents(question: str) -> dict:
    """Answer a question across this MCP session's documents. Returns {answer, sources}."""
    return answer_question(SESSION_ID, question)


if __name__ == "__main__":
    mcp.run()
