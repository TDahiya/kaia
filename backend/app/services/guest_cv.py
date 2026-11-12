"""The uploaded CV, used two ways.

The PDF is what `send_cv` attaches. The extracted text is what the knowledge
tools read. Deliberately no embeddings: a CV is a couple of pages and fits in
context whole, so retrieval could only ever lose information — the model
would sometimes get the education section and miss the experience.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_TEXT = 20_000


def _pdf_path() -> Path:
    return Path(get_settings().guest_cv_path or "/opt/kaia/data/cv.pdf")


def _txt_path() -> Path:
    return _pdf_path().with_suffix(".txt")


def save_cv(data: bytes) -> tuple[bool, str, int]:
    """Store the PDF and its text. Returns (ok, error, chars_extracted)."""
    pdf = _pdf_path()
    try:
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(data)
    except OSError as e:
        return False, f"Couldn't save the file: {e}", 0

    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception as e:
        logger.exception("cv: extraction failed")
        return False, f"Saved, but the text couldn't be read: {e}", 0

    if len(text) < 80:
        return False, (
            "No text could be extracted — this looks like a scanned image "
            "rather than a text PDF. Export it from the original document."
        ), 0

    try:
        _txt_path().write_text(text[:MAX_TEXT], encoding="utf-8")
    except OSError as e:
        return False, f"Couldn't save the extracted text: {e}", 0

    return True, "", len(text)


def cv_text() -> str:
    try:
        return _txt_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def cv_status() -> dict:
    pdf = _pdf_path()
    if not pdf.is_file():
        return {"uploaded": False}
    stat = pdf.stat()
    return {
        "uploaded": True,
        "filename": pdf.name,
        "size_bytes": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "extracted_chars": len(cv_text()),
    }
