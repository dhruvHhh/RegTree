"""
pageindex_builder.py

Builds a hierarchical section tree from pre-extracted text using Nemotron 3 Ultra (OpenRouter).
Saves the result to the session's trees folder and returns it as a dict.

Text must already exist in the session's text folder (produced by ingest/spark_job.py).

Public API:
    build_tree(session_id: str, doc_id: str) -> dict
"""

import json
import os
from openai import OpenAI

from storage import text_dir, trees_dir
from .config import OPENROUTER_API_KEY

_NEMOTRON_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
_MAX_CHARS_PER_CALL = 800_000  # ~200k tokens; stay well inside the 1M context


def _openrouter_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        timeout=45.0,
    )


def _load_cached_text(session_id: str, doc_id: str) -> dict[int, str]:
    """
    Read pre-extracted per-page text from the session's text folder
    (produced by ingest/spark_job.py). Returns a {page_number: text} dict.
    """
    text_path = os.path.join(text_dir(session_id), f"{doc_id}.json")
    if not os.path.exists(text_path):
        raise FileNotFoundError(
            f"No extracted text found at {text_path}. "
            f"Run text extraction first."
        )

    with open(text_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {p["page_number"]: p["text"] for p in data["pages"]}


def _build_full_text(pages: dict[int, str]) -> str:
    """Concatenate all pages with page markers."""
    parts = []
    for page_num in sorted(pages):
        parts.append(f"--- PAGE {page_num} ---\n{pages[page_num]}")
    return "\n\n".join(parts)


def _call_nemotron(client: OpenAI, prompt: str) -> str:
    response = client.chat.completions.create(
        model=_NEMOTRON_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    if not response.choices:
        # Free-tier models can return empty choices on rate limit or content filter
        raise RuntimeError(
            f"OpenRouter returned no choices. "
            f"Model: {response.model}, "
            f"Usage: {response.usage}, "
            f"Full response id: {response.id}"
        )
    return response.choices[0].message.content


def _build_prompt(doc_id: str, text_chunk: str, total_pages: int) -> str:
    return f"""You are analyzing a document with id "{doc_id}" ({total_pages} pages total).

Below is the full extracted text of the document, with page markers in the format "--- PAGE N ---".

Your task: return a JSON object representing the document's hierarchical section structure.
The JSON must exactly match this schema:

{{
  "doc_id": "<string>",
  "title": "<overall document title>",
  "children": [
    {{
      "node_id": "<string, e.g. '1', '1.1', '2'>",
      "title": "<section title>",
      "summary": "<one paragraph summary of what this section covers>",
      "start_page": <int>,
      "end_page": <int>,
      "children": [ ... ]
    }}
  ]
}}

Rules:
- Use "doc_id": "{doc_id}" exactly.
- Every leaf or non-leaf node must have start_page and end_page set to the actual page range the section spans.
- children may be empty [] for leaf sections.
- Respond with ONLY valid JSON. No markdown fences, no preamble, no commentary.

DOCUMENT TEXT:
{text_chunk}
"""


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from the model response, stripping any accidental markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip first and last fence line
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def build_tree(session_id: str, doc_id: str) -> dict:
    """
    Read pre-extracted text, build a hierarchical section tree via Nemotron 3 Ultra,
    save to the session's trees folder, and return the tree dict.
    """
    out_dir = trees_dir(session_id)
    os.makedirs(out_dir, exist_ok=True)
    tree_path = os.path.join(out_dir, f"{doc_id}.json")

    pages = _load_cached_text(session_id, doc_id)
    full_text = _build_full_text(pages)
    total_pages = max(pages.keys()) if pages else 0

    client = _openrouter_client()

    # Split into chunks only if the document is very long
    if len(full_text) <= _MAX_CHARS_PER_CALL:
        chunks = [full_text]
    else:
        # Split into at most a handful of equal-sized chunks
        chunk_size = _MAX_CHARS_PER_CALL
        chunks = [full_text[i: i + chunk_size] for i in range(0, len(full_text), chunk_size)]

    if len(chunks) == 1:
        prompt = _build_prompt(doc_id, chunks[0], total_pages)
        raw = _call_nemotron(client, prompt)
        tree = _parse_json_response(raw)
    else:
        # Multi-chunk: ask model to produce partial tree per chunk, merge top-level children
        all_children = []
        overall_title = None
        for idx, chunk in enumerate(chunks, start=1):
            prompt = _build_prompt(f"{doc_id}_part{idx}", chunk, total_pages)
            raw = _call_nemotron(client, prompt)
            partial = _parse_json_response(raw)
            all_children.extend(partial.get("children", []))
            if overall_title is None:
                overall_title = partial.get("title", doc_id)

        tree = {
            "doc_id": doc_id,
            "title": overall_title or doc_id,
            "children": all_children,
        }

    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    return tree
