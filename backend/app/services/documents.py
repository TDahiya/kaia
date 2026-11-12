"""Document storage, inspection, and sandboxed analysis.

Spreadsheets are answered by running real pandas over the real file rather
than retrieving text chunks — a retrieved chunk can only ever let the model
guess at a total, whereas running the code computes it.
"""

import logging
import os
import json
import asyncio
import tempfile
import subprocess
import sys
from pathlib import Path

from app.database import get_supabase

STORAGE_ROOT = Path(os.environ.get("KAIA_DOC_ROOT", "/opt/kaia/data/documents"))
RUNNER = Path(__file__).with_name("sandbox_runner.py")

# Unprivileged account used for guest-supplied code. Created by the deploy.
SANDBOX_USER = os.environ.get("KAIA_SANDBOX_USER", "kaia-sandbox")

logger = logging.getLogger(__name__)

TABLE_EXT = {".csv", ".tsv", ".xlsx", ".xlsm", ".xls", ".json"}
TEXT_EXT = {".pdf", ".txt", ".md"}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
EXEC_TIMEOUT_S = 25
MAX_TEXT_CHARS = 60_000


def classify(filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    if ext in TABLE_EXT:
        return "table"
    if ext in TEXT_EXT:
        return "text"
    return None


def storage_path_for(doc_id: str, filename: str) -> Path:
    # Keep the real extension (the loader dispatches on it) but never trust
    # the uploaded name for the path itself.
    return STORAGE_ROOT / f"{doc_id}{Path(filename).suffix.lower()}"


def save_bytes(doc_id: str, filename: str, data: bytes) -> Path:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    path = storage_path_for(doc_id, filename)
    path.write_bytes(data)
    return path


def get_document(doc_id: str, org_id: str) -> dict | None:
    r = (
        get_supabase().table("documents").select("*")
        .eq("id", doc_id).eq("org_id", org_id).execute()
    )
    return r.data[0] if r.data else None


def list_documents(conversation_id: str, org_id: str) -> list[dict]:
    r = (
        get_supabase().table("documents")
        .select("id, filename, kind, size_bytes, summary, created_at")
        .eq("conversation_id", conversation_id).eq("org_id", org_id)
        .order("created_at").execute()
    )
    return r.data or []


# ── Sandbox ────────────────────────────────────────────────────────────

def _drop_privileges():
    """Re-exec the child as an unprivileged user.

    The API runs as root, so without this the analysis process could read
    the backend's .env. Only used for untrusted code; returns None when the
    sandbox user does not exist so the owner's own path still works.
    """
    import pwd
    import os as _os

    entry = pwd.getpwnam(SANDBOX_USER)

    def _apply():
        _os.setgroups([])
        _os.setgid(entry.pw_gid)
        _os.setuid(entry.pw_uid)

    return _apply


def sandbox_user_available() -> bool:
    try:
        import pwd
        pwd.getpwnam(SANDBOX_USER)
        return True
    except (ImportError, KeyError):
        return False


async def run_analysis(data_path: str, code: str, untrusted: bool = False) -> dict:
    """Run pandas code against one file in a throwaway subprocess.

    `-I` drops env and cwd from the import path, the working directory is an
    empty temp dir, rlimits cap CPU/memory/file size, and the parent kills
    anything that overruns.

    With `untrusted=True` the child also drops to an unprivileged user so it
    cannot read the backend's secrets — required for anything a guest can
    reach. If that user is missing we refuse rather than silently running
    model-written code as root.
    """
    preexec = None
    if untrusted:
        if not sandbox_user_available():
            return {
                "ok": False, "output": "",
                "error": "Sandbox user is not configured, so this cannot run safely.",
            }
        preexec = _drop_privileges()

    with tempfile.TemporaryDirectory(prefix="kaia-analysis-") as tmp:
        code_file = Path(tmp) / "analysis.py"
        code_file.write_text(code, encoding="utf-8")
        if untrusted:
            # The dropped-privilege child still has to read these two files.
            Path(tmp).chmod(0o755)
            code_file.chmod(0o644)

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-I", str(RUNNER), str(data_path), str(code_file),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tmp,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": tmp,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    # Single-threaded BLAS: deterministic, lighter, and it
                    # keeps numpy well inside the process limit.
                    "OPENBLAS_NUM_THREADS": "1",
                    "OMP_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                    "NUMEXPR_NUM_THREADS": "1",
                },
                preexec_fn=preexec,
            )
        except Exception as e:
            return {"ok": False, "error": f"Could not start analysis: {e}", "output": ""}

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=EXEC_TIMEOUT_S)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "ok": False,
                "output": "",
                "error": f"Analysis timed out after {EXEC_TIMEOUT_S}s — try a narrower query.",
            }

    raw = stdout.decode(errors="replace").strip()
    if not raw:
        err = stderr.decode(errors="replace").strip()
        if err:
            # Surface the real reason. Claiming "memory limit" for every
            # silent failure once hid a startup crash for an entire deploy.
            logger.warning("analysis produced no stdout: %s", err[:500])
            return {"ok": False, "output": "", "error": f"Analysis failed to start — {err.splitlines()[-1][:200]}"}
        if proc.returncode and proc.returncode < 0:
            return {"ok": False, "output": "", "error": "Analysis exceeded its memory or CPU limit."}
        return {"ok": False, "output": "", "error": "Analysis produced no output."}

    try:
        return json.loads(raw.splitlines()[-1])
    except json.JSONDecodeError:
        return {"ok": False, "output": raw[:2000], "error": "Malformed result from analysis."}


INSPECT_CODE = """
import pandas as pd
if sheets:
    print(f"Workbook with {len(sheets)} sheet(s): {list(sheets)}")
    for name, sheet in sheets.items():
        print(f"\\n--- sheet: {name} — {len(sheet)} rows x {len(sheet.columns)} cols ---")
        print("columns:", list(sheet.columns))
        print(sheet.head(5).to_string())
else:
    print(f"{len(df)} rows x {len(df.columns)} cols")
    print("columns:", list(df.columns))
    print("\\ndtypes:")
    print(df.dtypes.to_string())
    print("\\nfirst rows:")
    print(df.head(5).to_string())
"""


async def inspect_table(data_path: str, untrusted: bool = False) -> dict:
    """Schema + a few rows, so the model writes code against reality."""
    return await run_analysis(data_path, INSPECT_CODE, untrusted=untrusted)


# ── Text extraction ────────────────────────────────────────────────────

def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            pages = [(p.extract_text() or "") for p in reader.pages]
            text = "\n\n".join(pages)
        except Exception as e:
            return f"[Could not read PDF: {e}]"
    else:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[Could not read file: {e}]"

    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + f"\n\n[truncated — {len(text)} chars total]"
    return text
