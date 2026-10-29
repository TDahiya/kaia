"""Google Sheets CRM — record contacts, leads, meetings, follow-ups."""

from datetime import datetime, timezone
from googleapiclient.discovery import build
from app.config import get_settings
from app.services.tool_registry import ToolDef, registry
from app.services.google_auth import get_google_credentials

CRM_HEADERS = [
    "ID", "Name", "Email", "Phone", "Organization", "Type",
    "Outcome", "Meeting Date", "Follow-up Date", "Notes", "Updated",
]


async def _get_sheets_service(user_id: str, org_id: str):
    creds = await get_google_credentials(user_id, org_id)
    if not creds:
        raise ValueError("Google Sheets not connected.")
    return build("sheets", "v4", credentials=creds)


async def _ensure_spreadsheet(user_id: str, org_id: str) -> str:
    """Get or create the CRM spreadsheet."""
    sid = get_settings().google_sheets_spreadsheet_id
    if sid:
        return sid

    creds = await get_google_credentials(user_id, org_id)
    if not creds:
        raise ValueError("Google not connected.")
    service = build("sheets", "v4", credentials=creds)
    spreadsheet = service.spreadsheets().create(body={
        "properties": {"title": "Kaia CRM"},
        "sheets": [{"properties": {"title": "Contacts"}}],
    }).execute()
    sid = spreadsheet["spreadsheetId"]

    service.spreadsheets().values().update(
        spreadsheetId=sid, range="Contacts!A1",
        valueInputOption="RAW",
        body={"values": [CRM_HEADERS]},
    ).execute()
    return sid


async def add_or_update_contact(
    name: str, email: str = "", phone: str = "", organization: str = "",
    contact_type: str = "lead", outcome: str = "", meeting_date: str = "",
    follow_up_date: str = "", notes: str = "", **ctx
) -> dict:
    service = await _get_sheets_service(ctx["user_id"], ctx["org_id"])
    sid = await _ensure_spreadsheet(ctx["user_id"], ctx["org_id"])

    result = service.spreadsheets().values().get(
        spreadsheetId=sid, range="Contacts!A:K"
    ).execute()
    rows = result.get("values", [])

    # Find existing by email or name (stable dedup)
    existing_row = None
    for i, row in enumerate(rows[1:], start=2):  # skip header
        if len(row) > 1 and (
            (email and len(row) > 2 and row[2].lower() == email.lower()) or
            row[1].lower() == name.lower()
        ):
            existing_row = i
            break

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    row_id = rows[existing_row - 1][0] if existing_row and rows[existing_row - 1] else f"C{len(rows)}"
    values = [[row_id, name, email, phone, organization, contact_type, outcome, meeting_date, follow_up_date, notes, now]]

    if existing_row:
        service.spreadsheets().values().update(
            spreadsheetId=sid, range=f"Contacts!A{existing_row}",
            valueInputOption="RAW", body={"values": values},
        ).execute()
        return {"success": True, "action": "updated", "row": existing_row}
    else:
        service.spreadsheets().values().append(
            spreadsheetId=sid, range="Contacts!A:K",
            valueInputOption="RAW", body={"values": values},
        ).execute()
        return {"success": True, "action": "added", "id": row_id}


async def search_contacts(query: str, **ctx) -> dict:
    service = await _get_sheets_service(ctx["user_id"], ctx["org_id"])
    sid = await _ensure_spreadsheet(ctx["user_id"], ctx["org_id"])

    result = service.spreadsheets().values().get(
        spreadsheetId=sid, range="Contacts!A:K"
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return {"contacts": [], "count": 0}

    headers = rows[0]
    matches = []
    for row in rows[1:]:
        if any(query.lower() in cell.lower() for cell in row if cell):
            contact = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            matches.append(contact)

    return {"contacts": matches[:20], "count": len(matches)}


for tool in [
    ToolDef(
        name="crm_add_or_update_contact",
        description="Add a new contact to the CRM or update an existing one. Deduplicates by email or name.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "organization": {"type": "string"},
                "contact_type": {"type": "string", "enum": ["lead", "client", "partner", "personal"]},
                "outcome": {"type": "string"},
                "meeting_date": {"type": "string"},
                "follow_up_date": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["name"],
        },
        executor=add_or_update_contact,
        category="google",
    ),
    ToolDef(
        name="crm_search_contacts",
        description="Search CRM contacts by name, email, organization, or any field.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
            },
            "required": ["query"],
        },
        executor=search_contacts,
        category="google",
    ),
]:
    registry.register(tool)
