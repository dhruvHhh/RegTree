"""
spark_job.py — PySpark ingestion job.

Extracts per-page text from the PDFs a session just uploaded, in parallel using
PySpark, and writes each result to that session's text folder:
    data/sessions/<session_id>/text/<doc_id>.json

Public API:
    extract_text_parallel(session_id: str, files: list[dict]) -> dict[str, str]
        where each file is {"doc_id": str, "pdf_path": str}. Returns a
        {doc_id: error_message} map for the files that failed to extract;
        files that succeeded have their text written to disk.
"""

import json
import os
import sys
import threading

import pdfplumber
from pyspark.sql import SparkSession

# Must be set before SparkSession is created, otherwise the JVM launches workers
# with whatever "python" is on PATH instead of this venv's interpreter.
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

# Spark allows only one active SparkContext per process. Uploads are processed
# on FastAPI's background-task thread pool, so two uploads close together can run
# concurrently. We therefore keep a single long-lived SparkSession (never stopped
# during normal operation) and serialize job execution with a lock, so one job
# can never tear down or collide with another's context.
_spark_lock = threading.Lock()
_spark: SparkSession | None = None


def _get_spark() -> SparkSession:
    global _spark
    if _spark is None:
        _spark = (
            SparkSession.builder
            .master("local[*]")
            .appName("rbi_pdf_text_extraction")
            .getOrCreate()
        )
    return _spark


def _extract_single_pdf(row: dict) -> dict:
    """
    Map function: given a dict with doc_id and pdf_path, extract per-page text.
    Returns {"doc_id", "pages"} on success, or {"doc_id", "error"} on failure —
    a failure is returned rather than raised so one bad PDF can't fail the whole
    Spark job.
    """

    doc_id = row["doc_id"]
    try:
        pages = []
        with pdfplumber.open(row["pdf_path"]) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages.append({"page_number": i, "text": page.extract_text() or ""})
        return {"doc_id": doc_id, "pages": pages}
    except Exception as e:
        return {"doc_id": doc_id, "error": str(e)}


def extract_text_parallel(session_id: str, files: list[dict]) -> dict[str, str]:
    """
    Use PySpark to extract per-page text from the given PDFs in parallel.
    `files` is a list of {"doc_id": str, "pdf_path": str} for the documents just
    uploaded in this request. Text for each successful file is written to the
    session's text folder; a {doc_id: error_message} map is returned for the
    files that failed to extract.
    """

    # Imported here (driver-side) rather than at module top so Spark workers
    # re-importing this module don't need `storage` on their path.
    from storage import text_dir

    out_dir = text_dir(session_id)
    os.makedirs(out_dir, exist_ok=True)

    # Only one Spark job runs at a time; the session is shared and never stopped.
    with _spark_lock:
        spark = _get_spark()
        rdd = spark.sparkContext.parallelize(files, numSlices=len(files))
        results = rdd.map(_extract_single_pdf).collect()

    # Writing text to disk is per-session and independent of Spark, so it runs
    # outside the lock to keep the serialized section as short as possible.
    errors: dict[str, str] = {}
    for doc in results:
        if "error" in doc:
            errors[doc["doc_id"]] = doc["error"]
            print(f"  FAILED {doc['doc_id']}: {doc['error']}")
            continue
        out_path = os.path.join(out_dir, f"{doc['doc_id']}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False)
        print(f"  Wrote {out_path} ({len(doc['pages'])} pages)")

    print(
        f"Text extraction complete for session {session_id} — "
        f"{len(results) - len(errors)} ok, {len(errors)} failed"
    )
    return errors
