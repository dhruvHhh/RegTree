"""Builds a document's hierarchical section tree from its extracted text via OpenRouter (Nemotron 3.5 Super VL, with a fallback)."""

import json
import os
import threading
import time
from openai import NotFoundError, OpenAI

from storage import text_dir, trees_dir
from .config import OPENROUTER_API_KEY

# Tried in order. The last is a different provider, so it isn't overloaded at the same moment
# as Nemotron; 512k context.
_MODELS = (
    "nvidia/nemotron-3.5-super-vl:free",
    "dots-studio/dots-3-note-preview:free",
)
_RETRY_DELAYS = (3, 6)  # seconds before the 2nd and 3rd attempt on each model
_TREE_TIME_LIMIT = 15 * 60  # seconds for one document's tree, all attempts and models combined
# ~200k tokens: well inside Nemotron 3.5 Super VL's 1M-token context, with room for the reply.
_MAX_CHARS_PER_CALL = 800_000


def _openrouter_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        timeout=45.0,
    )


def _load_cached_text(session_id: str, doc_id: str) -> dict[int, str]:
    """Return {page_number: text} from the session's extracted-text file."""
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


class _UnusableReply(Exception):
    """A successful HTTP reply with no usable tree: empty choices/content or invalid JSON."""


def _call_model(client: OpenAI, model: str, prompt: str) -> dict:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    # Free-tier models can return empty choices on rate limit or content filter
    if not response.choices or not response.choices[0].message.content:
        raise _UnusableReply(f"OpenRouter returned no choices (response id: {response.id})")
    try:
        return _parse_json_response(response.choices[0].message.content)
    except json.JSONDecodeError as exc:
        raise _UnusableReply(f"OpenRouter returned invalid JSON: {exc}") from exc


def _generate_tree(client: OpenAI, prompt: str, label: str) -> dict:
    """Get a tree from each model in turn, retrying unusable replies with backoff."""
    # Only unusable replies are retried here: the SDK already retries 429s, 5xx and timeouts,
    # and auth or other API errors should fail straight away. A 404 means the model was
    # withdrawn, so it skips straight to the next one.
    last_error = None
    for model in _MODELS:
        for attempt, delay in enumerate((0, *_RETRY_DELAYS), start=1):
            time.sleep(delay)
            try:
                tree = _call_model(client, model, prompt)
            except _UnusableReply as exc:
                last_error = exc
                print(f"  tree {label}: {model} attempt {attempt} failed: {exc}")
                continue
            except NotFoundError as exc:
                last_error = exc
                print(f"  tree {label}: {model} unavailable: {exc}")
                break
            print(f"  tree {label}: built with {model} on attempt {attempt}")
            return tree
    raise RuntimeError(f"{last_error}; gave up after retrying {', '.join(_MODELS)}")


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
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def _tree_from_chunks(client: OpenAI, doc_id: str, chunks: list[str], total_pages: int) -> dict:
    """Build the tree from one chunk, or merge the top-level sections of each chunk's partial tree."""
    if len(chunks) == 1:
        prompt = _build_prompt(doc_id, chunks[0], total_pages)
        return _generate_tree(client, prompt, doc_id)

    all_children = []
    overall_title = None
    for idx, chunk in enumerate(chunks, start=1):
        prompt = _build_prompt(f"{doc_id}_part{idx}", chunk, total_pages)
        partial = _generate_tree(client, prompt, f"{doc_id} part {idx}")
        all_children.extend(partial.get("children", []))
        if overall_title is None:
            overall_title = partial.get("title", doc_id)

    return {
        "doc_id": doc_id,
        "title": overall_title or doc_id,
        "children": all_children,
    }


def build_tree(session_id: str, doc_id: str) -> dict:
    """Build, save and return the section tree for one document."""
    out_dir = trees_dir(session_id)
    os.makedirs(out_dir, exist_ok=True)
    tree_path = os.path.join(out_dir, f"{doc_id}.json")

    pages = _load_cached_text(session_id, doc_id)
    full_text = _build_full_text(pages)
    total_pages = max(pages.keys()) if pages else 0

    client = _openrouter_client()

    if len(full_text) <= _MAX_CHARS_PER_CALL:
        chunks = [full_text]
    else:
        chunk_size = _MAX_CHARS_PER_CALL
        chunks = [full_text[i: i + chunk_size] for i in range(0, len(full_text), chunk_size)]

    result = {}

    def work() -> None:
        try:
            result["tree"] = _tree_from_chunks(client, doc_id, chunks, total_pages)
        except Exception as exc:
            result["error"] = exc

    # OpenRouter keeps slow calls alive, so no request timeout fires; run the model work on a
    # daemon thread and stop waiting at the time limit instead.
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(_TREE_TIME_LIMIT)
    if worker.is_alive():
        client.close()  # aborts the in-flight request so the abandoned thread ends
        raise TimeoutError(
            f"Timed out after {_TREE_TIME_LIMIT // 60} minutes building the document structure "
            f"(all attempts and models combined)."
        )
    if "error" in result:
        raise result["error"]
    tree = result["tree"]

    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    return tree
