"""PySpark job that extracts per-page text from uploaded PDFs in parallel."""

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

# Spark allows one SparkContext per process and uploads can run concurrently on FastAPI's
# thread pool, so keep one long-lived session and serialize jobs with a lock.
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
    """Spark map function; returns errors instead of raising so one bad PDF can't fail the job."""
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
    """Extract and save text for `files` ({doc_id, pdf_path}); return {doc_id: error} for failures."""
    # Imported here so Spark workers re-importing this module don't need `storage`.
    from storage import text_dir

    out_dir = text_dir(session_id)
    os.makedirs(out_dir, exist_ok=True)

    with _spark_lock:
        spark = _get_spark()
        rdd = spark.sparkContext.parallelize(files, numSlices=len(files))
        results = rdd.map(_extract_single_pdf).collect()

    # Disk writes don't need Spark, so they run outside the lock.
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
