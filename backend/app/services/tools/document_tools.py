"""Tools for reasoning over uploaded files.

Spreadsheets are never summarised into the prompt and guessed at — the
model inspects the real schema, writes pandas, and gets back computed
numbers. That is the difference between an answer and a plausible answer.
"""

from app.services.tool_registry import ToolDef, registry
from app.services import documents as docs


async def inspect_document(document_id: str = "", **ctx) -> dict:
    """Schema, size and sample rows for an uploaded file."""
    org_id = ctx.get("org_id", "")
    doc = docs.get_document(document_id, org_id)
    if not doc:
        return {"error": "No such document."}

    if doc["kind"] != "table":
        text = docs.extract_text(docs.Path(doc["storage_path"]))
        return {"filename": doc["filename"], "kind": "text", "content": text[:8000]}

    result = await docs.inspect_table(doc["storage_path"])
    if not result.get("ok"):
        return {"error": result.get("error", "Could not inspect the file.")}
    return {"filename": doc["filename"], "kind": "table", "schema": result["output"]}


async def query_document(document_id: str = "", code: str = "", **ctx) -> dict:
    """Run pandas against an uploaded table and return what it printed."""
    org_id = ctx.get("org_id", "")
    doc = docs.get_document(document_id, org_id)
    if not doc:
        return {"error": "No such document."}
    if doc["kind"] != "table":
        return {"error": "That file is not a table — read it with inspect_document instead."}
    if not code.strip():
        return {"error": "No code supplied."}

    result = await docs.run_analysis(doc["storage_path"], code)
    if not result.get("ok"):
        return {"error": result.get("error"), "output": result.get("output", "")}
    if not result["output"].strip():
        return {"error": "The code ran but printed nothing. Print the value you want."}
    return {"result": result["output"]}


registry.register(ToolDef(
    name="inspect_document",
    description=(
        "Look at an uploaded file before answering questions about it. For "
        "spreadsheets and CSVs this returns the real column names, dtypes, row "
        "count and first rows; for PDFs and text files it returns the content. "
        "Always call this before query_document so your code matches the actual "
        "columns rather than assumed ones."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "description": "id of the attached document"},
        },
        "required": ["document_id"],
    },
    executor=inspect_document,
    category="documents",
))

registry.register(ToolDef(
    name="query_document",
    description=(
        "Answer a question about an uploaded spreadsheet or CSV by running "
        "pandas over the real file. Never calculate totals, averages, counts or "
        "filters in your head from sample rows — write code and run it here, "
        "because only this returns the true figure.\n\n"
        "`df` is the table (first sheet for a workbook) and `sheets` is a dict "
        "of every sheet by name. `pd` is pandas. You only see what you print, "
        "so end with print(...)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "description": "id of the attached document"},
            "code": {
                "type": "string",
                "description": "Python using df / sheets / pd. Must print its result.",
            },
        },
        "required": ["document_id", "code"],
    },
    executor=query_document,
    category="documents",
))
