"""Turn model output into real files the user can download.

Input is lightweight markdown (headings, bullets, paragraphs) for prose
formats, or CSV text for the table formats. Nothing here executes model
code — the structure is parsed, not evaluated.
"""

import csv
import io
import hmac
import hashlib
from pathlib import Path

from app.config import get_settings

FORMATS = {"docx", "pdf", "xlsx", "csv", "md", "txt"}

EXT = {
    "docx": ".docx", "pdf": ".pdf", "xlsx": ".xlsx",
    "csv": ".csv", "md": ".md", "txt": ".txt",
}

MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "md": "text/markdown",
    "txt": "text/plain",
}


def _blocks(markdown: str):
    """Yield (kind, text) for each line. Deliberately small: headings,
    bullets and paragraphs cover what an assistant actually writes."""
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            yield ("blank", "")
        elif line.startswith("### "):
            yield ("h3", line[4:].strip())
        elif line.startswith("## "):
            yield ("h2", line[3:].strip())
        elif line.startswith("# "):
            yield ("h1", line[2:].strip())
        elif line.lstrip().startswith(("- ", "* ")):
            yield ("li", line.lstrip()[2:].strip())
        else:
            yield ("p", line.strip())


def _strip_emphasis(text: str) -> str:
    # The document's own styles carry the emphasis, so literal ** would
    # just show up as punctuation.
    return text.replace("**", "").replace("__", "")


def build_docx(title: str, content: str) -> bytes:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    if title:
        doc.add_heading(title, level=0)

    for kind, text in _blocks(content):
        text = _strip_emphasis(text)
        if kind == "blank":
            continue
        if kind == "h1":
            doc.add_heading(text, level=1)
        elif kind == "h2":
            doc.add_heading(text, level=2)
        elif kind == "h3":
            doc.add_heading(text, level=3)
        elif kind == "li":
            doc.add_paragraph(text, style="List Bullet")
        else:
            p = doc.add_paragraph(text)
            p.paragraph_format.space_after = Pt(8)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_pdf(title: str, content: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15.5)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=title or "Document",
    )

    flow = []
    if title:
        flow += [Paragraph(title, styles["Title"]), Spacer(1, 6 * mm)]

    bullets: list[str] = []

    def flush_bullets():
        if bullets:
            flow.append(ListFlowable(
                [ListItem(Paragraph(b, body)) for b in bullets],
                bulletType="bullet", leftIndent=12,
            ))
            flow.append(Spacer(1, 3 * mm))
            bullets.clear()

    for kind, text in _blocks(content):
        text = _strip_emphasis(text)
        if kind == "li":
            bullets.append(text)
            continue
        flush_bullets()
        if kind == "blank":
            flow.append(Spacer(1, 3 * mm))
        elif kind in ("h1", "h2", "h3"):
            flow.append(Paragraph(text, styles[{"h1": "Heading1", "h2": "Heading2", "h3": "Heading3"}[kind]]))
        else:
            flow.append(Paragraph(text, body))

    flush_bullets()
    doc.build(flow)
    return buf.getvalue()


def _rows(csv_text: str) -> list[list[str]]:
    return [r for r in csv.reader(io.StringIO(csv_text.strip())) if r]


def build_xlsx(title: str, csv_text: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = (title or "Sheet1")[:31]

    rows = _rows(csv_text)
    for r in rows:
        ws.append(r)

    if rows:
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        # Size columns to content so the file opens readable.
        for i in range(1, len(rows[0]) + 1):
            longest = max((len(str(r[i - 1])) for r in rows if len(r) >= i), default=10)
            ws.column_dimensions[get_column_letter(i)].width = min(max(longest + 2, 10), 55)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render(fmt: str, title: str, content: str) -> bytes:
    if fmt == "docx":
        return build_docx(title, content)
    if fmt == "pdf":
        return build_pdf(title, content)
    if fmt == "xlsx":
        return build_xlsx(title, content)
    if fmt == "csv":
        return content.encode("utf-8")
    return content.encode("utf-8")  # md / txt


def sign(doc_id: str) -> str:
    """Download links are clicked from a chat bubble, so they cannot carry
    an auth header. A signature keeps the URL unguessable on its own."""
    secret = (get_settings().jwt_secret or "kaia").encode()
    return hmac.new(secret, doc_id.encode(), hashlib.sha256).hexdigest()[:32]


def verify(doc_id: str, token: str) -> bool:
    return hmac.compare_digest(sign(doc_id), token or "")


def safe_name(name: str, fmt: str) -> str:
    """Keep the user's filename but never let it escape the storage dir."""
    base = Path(name or "document").name
    base = "".join(c for c in base if c.isalnum() or c in " ._-").strip() or "document"
    if base.lower().endswith(EXT[fmt]):
        base = base[: -len(EXT[fmt])]
    return base[:80] + EXT[fmt]


def _demo() -> None:
    assert safe_name("../../etc/passwd", "pdf") == "passwd.pdf"
    assert safe_name("report.docx", "docx") == "report.docx"
    assert safe_name("", "md") == "document.md"
    assert safe_name("a" * 200, "csv").endswith(".csv")
    assert verify("abc", sign("abc"))
    assert not verify("abc", sign("xyz"))
    assert _rows("a,b\n1,2\n") == [["a", "b"], ["1", "2"]]
    print("ok")


if __name__ == "__main__":
    _demo()
