"""Let Kaia hand back a real file instead of a wall of text."""

import uuid

from app.config import get_settings
from app.database import get_supabase
from app.services.tool_registry import ToolDef, registry
from app.services import documents as docs
from app.services import exporters


async def export_file(
    filename: str = "",
    format: str = "pdf",
    content: str = "",
    title: str = "",
    **ctx,
) -> dict:
    fmt = (format or "").lower().strip()
    if fmt not in exporters.FORMATS:
        return {"error": f"Unsupported format. Choose one of: {', '.join(sorted(exporters.FORMATS))}."}
    if not content.strip():
        return {"error": "No content supplied."}

    org_id = ctx.get("org_id", "")
    conversation_id = ctx.get("conversation_id")

    try:
        data = exporters.render(fmt, title or "", content)
    except Exception as e:
        return {"error": f"Could not build the {fmt} file — {type(e).__name__}: {e}"}

    doc_id = str(uuid.uuid4())
    name = exporters.safe_name(filename or title or "document", fmt)
    path = docs.save_bytes(doc_id, name, data)

    get_supabase().table("documents").insert({
        "id": doc_id,
        "org_id": org_id,
        "conversation_id": conversation_id,
        "filename": name,
        "content_type": exporters.MIME[fmt],
        "size_bytes": len(data),
        "kind": "table" if fmt in ("xlsx", "csv") else "text",
        "storage_path": str(path),
        "summary": f"Generated {fmt.upper()} — {name}",
    }).execute()

    base = get_settings().app_base_url.rstrip("/")
    url = f"{base}/api/documents/{doc_id}/download?t={exporters.sign(doc_id)}"

    return {
        "filename": name,
        "size_bytes": len(data),
        "download_url": url,
        "note": "Give the user this link as a markdown link so they can click it.",
    }


registry.register(ToolDef(
    name="export_file",
    description=(
        "Produce a downloadable file for the user: Word (docx), PDF, Excel "
        "(xlsx), CSV, Markdown or plain text. Use this whenever they ask for "
        "something 'as a document', 'as a spreadsheet', 'as a PDF', or want to "
        "save or send the result.\n\n"
        "For docx/pdf/md/txt, `content` is light markdown: '# ' and '## ' for "
        "headings, '- ' for bullets, blank lines between paragraphs.\n"
        "For xlsx/csv, `content` must be CSV text with a header row — if the "
        "numbers come from an uploaded spreadsheet, compute them with "
        "query_document first and build the CSV from the real output.\n\n"
        "Return the download_url to the user as a markdown link."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "e.g. 'Q3 summary' — extension added automatically"},
            "format": {
                "type": "string",
                "enum": ["docx", "pdf", "xlsx", "csv", "md", "txt"],
            },
            "title": {"type": "string", "description": "Heading inside the document"},
            "content": {"type": "string", "description": "Markdown body, or CSV text for xlsx/csv"},
        },
        "required": ["format", "content"],
    },
    executor=export_file,
    category="documents",
))
