"""
retrieval.py

Answers a question using the stored PageIndex trees and Groq (llama-3.3-70b-versatile).

Two Groq calls per question:
  1. Pick which node(s) are relevant (using titles + summaries only).
  2. Answer the question using the actual page text for those nodes.

Public API:
    answer_question(session_id: str, question: str) -> str

A session only ever loads trees and page text from its own folder, so it can
never see another session's documents or answers.
"""

import json
import os
from groq import Groq

from storage import text_dir, trees_dir
from .config import GROQ_API_KEY

_GROQ_MODEL = "llama-3.3-70b-versatile"


def _groq_client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)


def _load_trees(session_id: str) -> list[dict]:
    """Load all tree JSON files from this session's trees directory."""
    session_trees = trees_dir(session_id)
    if not os.path.isdir(session_trees):
        return []
    trees = []
    for fname in os.listdir(session_trees):
        if fname.endswith(".json"):
            with open(os.path.join(session_trees, fname), "r", encoding="utf-8") as f:
                trees.append(json.load(f))
    return trees


def _flatten_nodes(tree: dict) -> list[dict]:
    """Return a flat list of all nodes in the tree, each annotated with doc_id."""
    result = []

    def walk(node: dict):
        result.append({
            "doc_id": tree["doc_id"],
            "node_id": node.get("node_id", "root"),
            "title": node.get("title", ""),
            "summary": node.get("summary", ""),
            "start_page": node.get("start_page"),
            "end_page": node.get("end_page"),
        })
        for child in node.get("children", []):
            walk(child)

    # top-level tree nodes are in "children"
    for child in tree.get("children", []):
        walk(child)
    return result


def _tree_summary_text(trees: list[dict]) -> str:
    """Build a compact text representation of all nodes (titles + summaries only)."""
    lines = []
    for tree in trees:
        lines.append(f"=== Document: {tree['doc_id']} — {tree.get('title', '')} ===")
        for node in _flatten_nodes(tree):
            lines.append(
                f"  [{node['doc_id']}::{node['node_id']}] {node['title']} "
                f"(pages {node['start_page']}–{node['end_page']})\n"
                f"    {node['summary']}"
            )
    return "\n".join(lines)


def _pick_nodes_prompt(question: str, tree_summary: str) -> str:
    return f"""You are a document retrieval assistant.

Below is a summary of all indexed document sections (titles and summaries only — no full text):

{tree_summary}

Question: {question}

Identify which section(s) most likely contain the answer.
Respond with a JSON array of objects, each with "doc_id" and "node_id". Example:
[{{"doc_id": "rbi_circular_2026_04", "node_id": "2.1"}}]

Respond with ONLY the JSON array. No explanation, no markdown fences.
"""


def _load_page_text(session_id: str, doc_id: str, start_page: int, end_page: int) -> str:
    """
    Load page text for the given page range from this session's text folder
    (produced by ingest/spark_job.py).
    """
    text_path = os.path.join(text_dir(session_id), f"{doc_id}.json")
    if not os.path.exists(text_path):
        return ""

    with open(text_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build a page_number -> text lookup from the spark_job format
    page_map = {p["page_number"]: p["text"] for p in data["pages"]}
    parts = []
    for p in range(start_page, end_page + 1):
        text = page_map.get(p, "")
        if text:
            parts.append(f"--- PAGE {p} ---\n{text}")
    return "\n\n".join(parts)


def _answer_prompt(question: str, context: str) -> str:
    return f"""You are a helpful assistant answering questions about regulatory documents.

Use only the text below to answer the question. If the answer isn't present, say so clearly.

CONTEXT:
{context}

QUESTION: {question}

Answer:"""


def answer_question(session_id: str, question: str) -> dict:
    """
    Answer a question using only this session's documents by:
    1. Loading the session's indexed trees.
    2. Asking Groq to pick the relevant node(s) (titles + summaries only).
    3. Loading the actual page text for those nodes.
    4. Asking Groq to answer the question using that text.
    Returns {"answer": str, "sources": [{"doc_id", "node_id", "title"}]}; sources
    is empty when no section could be used to answer.
    """
    trees = _load_trees(session_id)
    if not trees:
        return {
            "answer": "No documents have been uploaded yet. Upload a document first.",
            "sources": [],
        }

    client = _groq_client()
    tree_summary = _tree_summary_text(trees)

    # --- Call 1: pick relevant nodes ---
    pick_response = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[{"role": "user", "content": _pick_nodes_prompt(question, tree_summary)}],
        temperature=0,
    )
    raw_picks = pick_response.choices[0].message.content.strip()

    try:
        picks = json.loads(raw_picks)
    except json.JSONDecodeError:
        picks = []

    if not picks:
        return {
            "answer": "Could not identify a relevant section for this question.",
            "sources": [],
        }

    # Build a lookup of all nodes across all trees
    all_nodes: dict[tuple[str, str], dict] = {}
    for tree in trees:
        for node in _flatten_nodes(tree):
            all_nodes[(node["doc_id"], node["node_id"])] = node

    # Gather page text for each picked node
    context_parts = []
    sources = []
    for pick in picks:
        doc_id = pick.get("doc_id", "")
        node_id = pick.get("node_id", "")
        # Groq may echo back "doc_id::node_id" from the summary format; strip the prefix.
        if "::" in node_id:
            node_id = node_id.split("::", 1)[1]
        node = all_nodes.get((doc_id, node_id))
        if node and node["start_page"] is not None and node["end_page"] is not None:
            text = _load_page_text(session_id, doc_id, node["start_page"], node["end_page"])
            if text:
                context_parts.append(
                    f"[Source: {doc_id} — {node['title']}]\n{text}"
                )
                sources.append({"doc_id": doc_id, "node_id": node_id, "title": node["title"]})

    if not context_parts:
        return {
            "answer": "The relevant section was identified but its text could not be loaded.",
            "sources": [],
        }

    context = "\n\n".join(context_parts)

    # --- Call 2: answer the question ---
    answer_response = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[{"role": "user", "content": _answer_prompt(question, context)}],
        temperature=0,
    )
    return {
        "answer": answer_response.choices[0].message.content.strip(),
        "sources": sources,
    }
