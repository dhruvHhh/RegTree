"""
mcp_server.py — MCP server exposing RegTree as tools for Claude Desktop.

A second front door onto the same core logic the FastAPI backend already uses
(storage.py, ingest/spark_job.py, rag/pageindex_builder.py, rag/retrieval.py) —
no duplicate logic, just a different caller. Runs as its own stdio process,
independent of `uvicorn main:app`; both can run at once against the same data.

MCP clients aren't browsers and don't carry cookies, so instead of a per-request
session cookie this server uses one persistent local session id cached in
backend/.mcp_session_id. It is intentionally separate from any web-app session —
documents uploaded here and via the web UI don't mix.

Run:
    .\\venv\\Scripts\\python.exe mcp_server.py
"""

import sys
import os

# Claude Desktop launches this script from a different working directory. Put this
# folder on sys.path for the driver's own imports, AND on PYTHONPATH as a real env
# var so Spark's worker subprocesses — separate OS processes that don't inherit
# sys.path changes, only environment variables — can also resolve the ingest/rag/
# storage packages. Must run before pyspark is imported (via ingest.spark_job).
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

    # The Spark job prints progress to stdout; under MCP's stdio transport stdout
    # is the JSON-RPC channel. Wrap ONLY the noisy pipeline calls so their prints
    # go to stderr — every return and anything FastMCP writes stays outside this
    # block, so the tool's response is never redirected.
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
