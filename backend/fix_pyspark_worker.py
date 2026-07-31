"""Patch PySpark's worker so it flushes its socket before exiting.

Why this is needed
------------------
On native Windows with CPython 3.12, `pyspark/worker.py` writes the task
results into a 64 KB buffered socket writer and then simply falls off the end
of `__main__`. The interpreter can tear the socket down during finalization
before that buffer drains, so the ~100 bytes of results never reach the JVM.
Spark then reads EOF and reports:

    org.apache.spark.SparkException: Python worker exited unexpectedly (crashed)
    Caused by: java.io.EOFException

The worker itself raises no error -- it completes the whole protocol -- which
is why the failure looks like a silent crash.

Spark puts `python/lib/pyspark.zip` ahead of site-packages on the worker's
PYTHONPATH, so the copy inside that zip is the one actually imported. Both
copies are patched here.

Re-run this after any `pip install`/upgrade of pyspark. It is idempotent.

    python fix_pyspark_worker.py
"""

import os
import shutil
import sys
import zipfile

# Stable tag used to detect an already-applied patch (old or new); the full
# marker written into new patches carries the project name.
_PATCH_TAG = "windows worker flush fix"
MARKER = f"regtree {_PATCH_TAG}"

ORIGINAL = "    main(sock_file, sock_file)\n"

PATCHED = (
    "    # --- " + MARKER + " ---\n"
    "    # Windows/CPython 3.12 can close the socket during interpreter\n"
    "    # shutdown before the buffered writer drains, which makes the JVM\n"
    "    # see EOF and report 'Python worker exited unexpectedly'. Flushing\n"
    "    # explicitly guarantees the results reach the JVM. The finally block\n"
    "    # also covers main()'s sys.exit(-1) error path, which needs to get\n"
    "    # its serialized traceback out too.\n"
    "    try:\n"
    "        main(sock_file, sock_file)\n"
    "    finally:\n"
    "        try:\n"
    "            sock_file.flush()\n"
    "        except Exception:\n"
    "            pass\n"
)


def patch_source(src: str) -> str:
    if _PATCH_TAG in src:
        return src
    if ORIGINAL not in src:
        raise RuntimeError(
            "could not find the expected 'main(sock_file, sock_file)' line; "
            "pyspark layout may have changed"
        )
    # Only the __main__ invocation should match, but guard against surprises.
    if src.count(ORIGINAL) != 1:
        raise RuntimeError(f"expected exactly 1 match, found {src.count(ORIGINAL)}")
    return src.replace(ORIGINAL, PATCHED)


def patch_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if _PATCH_TAG in src:
        print(f"  already patched: {path}")
        return False
    new = patch_source(src)
    shutil.copy2(path, path + ".orig")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print(f"  PATCHED: {path}  (backup at {os.path.basename(path)}.orig)")
    return True


def patch_zip(zip_path: str, member: str = "pyspark/worker.py") -> bool:
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if member not in names:
            raise RuntimeError(f"{member} not found in {zip_path}")
        src = z.read(member).decode("utf-8")
        if _PATCH_TAG in src:
            print(f"  already patched: {zip_path}!{member}")
            return False
        entries = [(z.getinfo(n), z.read(n)) for n in names]

    new_src = patch_source(src).encode("utf-8")
    shutil.copy2(zip_path, zip_path + ".orig")

    tmp = zip_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for info, data in entries:
            out.writestr(info, new_src if info.filename == member else data)
    os.replace(tmp, zip_path)
    print(f"  PATCHED: {zip_path}!{member}  (backup at {os.path.basename(zip_path)}.orig)")
    return True


def main() -> int:
    import pyspark

    pkg_dir = os.path.dirname(pyspark.__file__)
    worker_py = os.path.join(pkg_dir, "worker.py")
    zip_path = os.path.join(pkg_dir, "python", "lib", "pyspark.zip")

    print(f"pyspark {pyspark.__version__} at {pkg_dir}")
    patch_file(worker_py)
    patch_zip(zip_path)
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
