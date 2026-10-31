"""FastAPI server for RegTree; documents are scoped per anonymous session cookie."""

import os
import sys

# Spark workers are separate processes that inherit env vars but not sys.path, so the
# backend dir goes on PYTHONPATH too. Must run before pyspark is imported.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

existing = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = BACKEND_DIR + (os.pathsep + existing if existing else "")

import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ingest.spark_job import extract_text_parallel
from rag.pageindex_builder import build_tree
from rag.retrieval import answer_question
from session import get_session_id
from storage import (
    add_sample_documents,
    load_manifest,
    raw_pdfs_dir,
    record_document,
    set_document_status,
    trees_dir,
)

app = FastAPI(title="RegTree API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,  # required for the session cookie to be sent/received
    allow_methods=["*"],
    allow_headers=["*"],
)


# Swagger UI shows OpenAPI 3.1 `contentMediaType` uploads as a text box; `format: binary`
# restores the file picker.
def _use_binary_format(node) -> None:
    if isinstance(node, dict):
        if node.get("type") == "string" and node.get("contentMediaType") == "application/octet-stream":
            node.pop("contentMediaType", None)
            node["format"] = "binary"
        for value in node.values():
            _use_binary_format(value)
    elif isinstance(node, list):
        for item in node:
            _use_binary_format(item)


def _custom_openapi() -> dict:
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        _use_binary_format(schema)
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi

# Everything lives under /api so it can't collide with React Router routes like /documents.
api = APIRouter(prefix="/api")


class QueryRequest(BaseModel):
    question: str


class Source(BaseModel):
    doc_id: str
    node_id: str
    title: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


def _safe_doc_id(doc_id: str) -> str:
    """Validate a doc_id from the URL as a uuid before using it in a path."""
    try:
        return str(uuid.UUID(doc_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document id.")


@api.get("/health")
def health():
    return {"status": "ok"}


def _process_upload(session_id: str, uploaded: list[dict]) -> None:
    """Extract text for the batch, build each tree, and record per-file status."""
    try:
        errors = extract_text_parallel(session_id, uploaded)
    except Exception as exc:
        # A Spark-level failure (not a single bad file) fails the whole batch.
        for u in uploaded:
            set_document_status(session_id, u["doc_id"], "failed", str(exc))
        return

    for u in uploaded:
        doc_id = u["doc_id"]
        if doc_id in errors:
            set_document_status(session_id, doc_id, "failed", errors[doc_id])
            continue
        try:
            build_tree(session_id, doc_id)
            set_document_status(session_id, doc_id, "ready")
        except Exception as exc:
            set_document_status(session_id, doc_id, "failed", str(exc))


@api.post("/documents")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    session_id: str = Depends(get_session_id),
):
    """Save uploaded PDFs as "processing" and process them in the background."""
    raw_dir = raw_pdfs_dir(session_id)
    os.makedirs(raw_dir, exist_ok=True)

    uploaded = []
    for f in files:
        doc_id = str(uuid.uuid4())
        pdf_path = os.path.join(raw_dir, f"{doc_id}.pdf")
        with open(pdf_path, "wb") as out:
            out.write(await f.read())
        record_document(session_id, doc_id, f.filename)
        uploaded.append({"doc_id": doc_id, "filename": f.filename, "pdf_path": pdf_path})

    background_tasks.add_task(_process_upload, session_id, uploaded)

    return {
        "documents": [
            {"doc_id": u["doc_id"], "filename": u["filename"], "status": "processing"}
            for u in uploaded
        ]
    }


@api.get("/documents")
def list_documents(session_id: str = Depends(get_session_id)):
    """List this session's documents with their processing status."""
    return [
        {"doc_id": d["doc_id"], "filename": d["filename"], "status": d.get("status", "unknown")}
        for d in load_manifest(session_id)
    ]


@api.get("/documents/{doc_id}/status")
def get_document_status(doc_id: str, session_id: str = Depends(get_session_id)):
    """Return one document's processing status (with error message if failed)."""
    doc_id = _safe_doc_id(doc_id)
    for d in load_manifest(session_id):
        if d["doc_id"] == doc_id:
            status = d.get("status", "unknown")
            result = {"doc_id": doc_id, "status": status}
            if status == "failed":
                result["error"] = d.get("error")
            return result
    raise HTTPException(status_code=404, detail="Document not found.")


@api.get("/documents/{doc_id}/tree")
def get_document_tree(doc_id: str, session_id: str = Depends(get_session_id)):
    """Return the section tree JSON for one of this session's documents."""
    doc_id = _safe_doc_id(doc_id)
    tree_path = os.path.join(trees_dir(session_id), f"{doc_id}.json")
    if not os.path.exists(tree_path):
        raise HTTPException(status_code=404, detail="Tree not found for this document.")
    with open(tree_path, "r", encoding="utf-8") as f:
        return json.load(f)


@api.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, session_id: str = Depends(get_session_id)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    result = answer_question(session_id, req.question)
    return QueryResponse(answer=result["answer"], sources=result["sources"])


@api.post("/samples")
def load_samples(session_id: str = Depends(get_session_id)):
    """Copy the bundled sample documents into this session, ready to query."""
    return {"documents": add_sample_documents(session_id)}


app.include_router(api)

# In production this app serves the built frontend; in dev Vite does and dist may not exist.
_DIST_DIR = os.path.realpath(os.path.join(BACKEND_DIR, "..", "frontend", "dist"))

if os.path.isdir(_DIST_DIR):
    # A missing hashed asset should 404, not return index.html as a script.
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST_DIR, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        """Serve a file from dist, or index.html so React Router can handle the route."""
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        file_path = os.path.realpath(os.path.join(_DIST_DIR, path))
        if file_path.startswith(_DIST_DIR + os.sep) and os.path.isfile(file_path):
            return FileResponse(file_path)
        # index.html names the hashed assets, so a cached copy would break after a redeploy.
        return FileResponse(os.path.join(_DIST_DIR, "index.html"), headers={"Cache-Control": "no-cache"})
