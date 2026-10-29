"""Gmail tools — search, read, draft, send emails."""

import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from app.services.tool_registry import ToolDef, registry
from app.services.google_auth import get_google_credentials


async def _get_gmail_service(user_id: str, org_id: str):
    creds = await get_google_credentials(user_id, org_id)
    if not creds:
        raise ValueError("Gmail not connected. Please authorize Google in Settings.")
    return build("gmail", "v1", credentials=creds)


async def search_emails(query: str, max_results: int = 5, **ctx) -> dict:
    service = await _get_gmail_service(ctx["user_id"], ctx["org_id"])
    result = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = []
    for msg_ref in result.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        messages.append({
            "id": msg["id"],
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "snippet": msg.get("snippet", ""),
        })
    return {"emails": messages, "count": len(messages)}


async def read_email(message_id: str, **ctx) -> dict:
    service = await _get_gmail_service(ctx["user_id"], ctx["org_id"])
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    body = ""
    payload = msg.get("payload", {})
    if payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    elif payload.get("parts"):
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break

    return {
        "id": msg["id"],
        "subject": headers.get("Subject", ""),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "date": headers.get("Date", ""),
        "body": body[:3000],
        "labels": msg.get("labelIds", []),
    }


async def create_draft(to: str, subject: str, body: str, **ctx) -> dict:
    service = await _get_gmail_service(ctx["user_id"], ctx["org_id"])
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    return {"success": True, "draft_id": draft["id"], "message": f"Draft created: '{subject}' to {to}"}


async def send_email(to: str, subject: str, body: str, **ctx) -> dict:
    service = await _get_gmail_service(ctx["user_id"], ctx["org_id"])
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return {"success": True, "message_id": sent["id"], "message": f"Email sent to {to}"}


for tool in [
    ToolDef(
        name="search_emails",
        description="Search Gmail for emails matching a query (same syntax as Gmail search).",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query, e.g. 'is:unread from:john'"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        executor=search_emails,
        category="google",
    ),
    ToolDef(
        name="read_email",
        description="Read the full content of a specific email by its message ID.",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Gmail message ID"},
            },
            "required": ["message_id"],
        },
        executor=read_email,
        category="google",
    ),
    ToolDef(
        name="create_email_draft",
        description="Create a Gmail draft (does NOT send). User must review and approve sending.",
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
        executor=create_draft,
        category="google",
    ),
    ToolDef(
        name="send_email",
        description="Send an email via Gmail. ONLY use when the user has explicitly authorized sending.",
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
        executor=send_email,
        requires_confirmation=True,
        category="google",
    ),
]:
    registry.register(tool)
