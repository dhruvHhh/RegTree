"""Per-session on-disk layout under data/sessions/<session_id>/ (ids must already be validated)."""

import json
import os
import shutil

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BACKEND_DIR, "data")
# Same layout as a session directory, with documents.json listing each sample's doc_id and filename.
_SAMPLES_DIR = os.path.join(_BACKEND_DIR, "samples")


def session_dir(session_id: str) -> str:
    return os.path.join(_DATA_DIR, "sessions", session_id)


def raw_pdfs_dir(session_id: str) -> str:
    return os.path.join(session_dir(session_id), "raw_pdfs")


def text_dir(session_id: str) -> str:
    return os.path.join(session_dir(session_id), "text")


def trees_dir(session_id: str) -> str:
    return os.path.join(session_dir(session_id), "trees")


# doc_ids are opaque uuids, so a per-session manifest maps each to its filename and status.
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


def add_sample_documents(session_id: str) -> list[dict]:
    """Copy the bundled samples into this session as ready, skipping any it already has."""
    with open(os.path.join(_SAMPLES_DIR, "documents.json"), "r", encoding="utf-8") as f:
        samples = json.load(f)

    manifest = load_manifest(session_id)
    existing = {entry["doc_id"] for entry in manifest}
    for sample in samples:
        doc_id = sample["doc_id"]
        if doc_id in existing:
            continue
        for folder, dest_dir, ext in (
            ("raw_pdfs", raw_pdfs_dir(session_id), ".pdf"),
            ("text", text_dir(session_id), ".json"),
            ("trees", trees_dir(session_id), ".json"),
        ):
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copyfile(
                os.path.join(_SAMPLES_DIR, folder, f"{doc_id}{ext}"),
                os.path.join(dest_dir, f"{doc_id}{ext}"),
            )
        manifest.append({"doc_id": doc_id, "filename": sample["filename"], "status": "ready"})
    _write_manifest(session_id, manifest)
    return [{**sample, "status": "ready"} for sample in samples]
