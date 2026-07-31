"""
storage.py — per-session, on-disk layout for uploaded documents.

Everything a session owns lives under a single folder keyed by its session id:

    data/sessions/<session_id>/
        raw_pdfs/         uploaded PDFs, named <doc_id>.pdf
        text/             extracted per-page text, <doc_id>.json
        trees/            section trees, <doc_id>.json
        documents.json    manifest mapping doc_id -> original filename

This module is the single source of truth for those paths. Callers must pass
a session id that has already been validated (see session.get_session_id); the
paths here are joined verbatim.
"""

import json
import os

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def session_dir(session_id: str) -> str:
    return os.path.join(_DATA_DIR, "sessions", session_id)


def raw_pdfs_dir(session_id: str) -> str:
    return os.path.join(session_dir(session_id), "raw_pdfs")


def text_dir(session_id: str) -> str:
    return os.path.join(session_dir(session_id), "text")


def trees_dir(session_id: str) -> str:
    return os.path.join(session_dir(session_id), "trees")


# ── Document manifest ────────────────────────────────────────────────────────
# doc_ids are opaque uuids, so we keep a small per-session manifest recording
# each document's original filename and processing status. An entry is:
#     {"doc_id", "filename", "status": "processing"|"ready"|"failed"}
# with an extra "error" key present only while status is "failed".

def _manifest_path(session_id: str) -> str:
    return os.path.join(session_dir(session_id), "documents.json")


def _write_manifest(session_id: str, manifest: list[dict]) -> None:
    os.makedirs(session_dir(session_id), exist_ok=True)
    with open(_manifest_path(session_id), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def load_manifest(session_id: str) -> list[dict]:
    """Return the list of document entries for this session, or [] if none yet."""
    path = _manifest_path(session_id)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def record_document(session_id: str, doc_id: str, filename: str) -> None:
    """Add a newly uploaded document to the manifest, marked as processing."""
    manifest = load_manifest(session_id)
    manifest.append({"doc_id": doc_id, "filename": filename, "status": "processing"})
    _write_manifest(session_id, manifest)


def set_document_status(
    session_id: str, doc_id: str, status: str, error: str | None = None
) -> None:
    """Update a document's status, attaching an error message when it failed."""
    manifest = load_manifest(session_id)
    for entry in manifest:
        if entry["doc_id"] == doc_id:
            entry["status"] = status
            if error is None:
                entry.pop("error", None)
            else:
                entry["error"] = error
            break
    _write_manifest(session_id, manifest)
