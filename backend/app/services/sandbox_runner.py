"""Executed as a SUBPROCESS, never imported by the app.

Runs model-written pandas against one data file and reports what it printed.
Invoked as:  python -I sandbox_runner.py <data_path> <code_path>
Replies with a single JSON object on stdout.

Limits are applied before pandas is imported so a runaway allocation dies
here rather than taking the API process down with it.
"""

import sys
import json
import io
import contextlib

MAX_OUTPUT = 8000


def _apply_limits() -> None:
    try:
        import resource
    except ImportError:  # non-POSIX; the timeout in the parent still applies
        return
    resource.setrlimit(resource.RLIMIT_CPU, (10, 12))
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024,) * 2)
    # Bounds a fork bomb without blocking numpy. Zero here is fatal: root
    # ignores the limit but an unprivileged child does not, and OpenBLAS
    # cannot start its threads, so `import pandas` dies before any user
    # code runs. The env also pins BLAS to one thread (see documents.py).
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))


def _load(path: str):
    """Return (df, sheets). `sheets` is empty for single-table formats."""
    import pandas as pd

    low = path.lower()
    if low.endswith((".xlsx", ".xlsm", ".xls")):
        sheets = pd.read_excel(path, sheet_name=None)
        first = next(iter(sheets.values())) if sheets else pd.DataFrame()
        return first, sheets
    if low.endswith(".tsv"):
        return pd.read_csv(path, sep="\t"), {}
    if low.endswith(".json"):
        return pd.read_json(path), {}
    return pd.read_csv(path), {}


def main() -> int:
    _apply_limits()

    data_path, code_path = sys.argv[1], sys.argv[2]
    with open(code_path, "r", encoding="utf-8") as fh:
        code = fh.read()

    result = {"ok": True, "output": "", "error": None}

    try:
        import pandas as pd
        pd.set_option("display.max_rows", 60)
        pd.set_option("display.max_columns", 50)
        pd.set_option("display.width", 200)
        df, sheets = _load(data_path)
    except Exception as e:
        print(json.dumps({"ok": False, "output": "", "error": f"Could not read the file — {type(e).__name__}: {e}"}))
        return 0

    env = {"__builtins__": __builtins__, "pd": pd, "df": df, "sheets": sheets}
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<analysis>", "exec"), env)
    except Exception as e:
        result["ok"] = False
        result["error"] = f"{type(e).__name__}: {e}"

    out = buf.getvalue()
    if len(out) > MAX_OUTPUT:
        out = out[:MAX_OUTPUT] + f"\n… truncated, {len(out)} chars total"
    result["output"] = out

    # The redirect has ended, so this reaches the real stdout.
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
