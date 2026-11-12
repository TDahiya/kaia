"""Upload and manage files attached to a conversation."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.auth import get_current_user
from app.database import get_supabase
from app.services import documents as docs
from app.services import exporters

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    conversation_id: str = Form(None),
    user: dict = Depends(get_current_user),
):
    kind = docs.classify(file.filename or "")
    if kind is None:
        raise HTTPException(
            400,
            "Unsupported file type. Upload a spreadsheet (.xlsx, .csv, .tsv), "
            "a PDF, or a text file.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(400, "That file is empty.")
    if len(data) > docs.MAX_UPLOAD_BYTES:
        raise HTTPException(
            400, f"File is too large — limit is {docs.MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
        )

    doc_id = str(uuid.uuid4())
    path = docs.save_bytes(doc_id, file.filename or "upload", data)

    # A one-line summary now means the model knows what it has without
    # having to open every attachment on every turn.
    summary = None
    if kind == "table":
        probe = await docs.inspect_table(str(path))
        if probe.get("ok"):
            summary = probe["output"][:1500]
    else:
        summary = docs.extract_text(path)[:1500]

    row = {
        "id": doc_id,
        "org_id": user["org_id"],
        "conversation_id": conversation_id or None,
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(data),
        "kind": kind,
        "storage_path": str(path),
        "summary": summary,
    }
    get_supabase().table("documents").insert(row).execute()

    return {
        "id": doc_id,
        "filename": file.filename,
        "kind": kind,
        "size_bytes": len(data),
        "summary": summary,
    }


@router.get("")
async def list_for_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    return {"documents": docs.list_documents(conversation_id, user["org_id"])}


@router.get("/{document_id}/download")
async def download_document(document_id: str, t: str = ""):
    """Served to a plain browser click, so it authenticates on the signed
    token in the URL rather than an Authorization header."""
    if not exporters.verify(document_id, t):
        raise HTTPException(403, "Invalid or missing download token")

    r = get_supabase().table("documents").select("*").eq("id", document_id).execute()
    if not r.data:
        raise HTTPException(404, "Document not found")
    doc = r.data[0]

    path = Path(doc["storage_path"])
    if not path.is_file():
        raise HTTPException(404, "File is no longer on disk")

    return FileResponse(
        path,
        media_type=doc.get("content_type") or "application/octet-stream",
        filename=doc["filename"],
    )


@router.delete("/{document_id}")
async def delete_document(document_id: str, user: dict = Depends(get_current_user)):
    doc = docs.get_document(document_id, user["org_id"])
    if not doc:
        raise HTTPException(404, "Document not found")

    try:
        Path(doc["storage_path"]).unlink(missing_ok=True)
    except OSError:
        pass  # row still goes, so it stops appearing in the UI

    get_supabase().table("documents").delete().eq("id", document_id).execute()
    return {"success": True}
