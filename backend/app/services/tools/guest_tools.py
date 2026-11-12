"""Tools the guest portal is allowed to call.

Registered in a separate registry from the owner's tools. Nothing here can
reach Tanishq's accounts on a visitor's behalf: email is templated and only
ever goes to the address the visitor themselves gave, calendar is never read,
and there is no memory write or code execution.
"""

import re
from pathlib import Path

from app.config import get_settings
from app.database import get_supabase
from app.services.tool_registry import ToolRegistry, ToolDef

# Separate registry — the owner's tools are never reachable from here.
guest_registry = ToolRegistry()

CONTENT = Path(__file__).resolve().parents[2] / "content" / "guest_profile.md"
REPO_ROOT = Path(__file__).resolve().parents[3]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")

# RFC 2606 reserves these, so mail to them always bounces. The model will
# happily invent one rather than admit it wasn't given an address.
PLACEHOLDER_DOMAINS = {
    "example.com", "example.org", "example.net", "example.edu",
    "test.com", "test.org", "domain.com", "yourdomain.com",
    "email.com", "sample.com", "mydomain.com", "localhost",
}
PLACEHOLDER_LOCALS = {
    "visitor", "someone", "guest", "user", "youremail", "your.email",
    "recruiter", "name", "firstname", "example", "test", "placeholder",
}


def valid_email(addr: str) -> tuple[bool, str]:
    """Syntax plus a check that it isn't a made-up stand-in."""
    addr = (addr or "").strip()
    if not EMAIL_RE.match(addr):
        return False, "That doesn't look like a valid email address."

    local, _, domain = addr.rpartition("@")
    if domain.lower() in PLACEHOLDER_DOMAINS or local.lower() in PLACEHOLDER_LOCALS:
        return False, (
            "I don't have their real email address yet — ask for it and use "
            "exactly what they give you. Never fill in a placeholder."
        )
    return True, ""


def _sections() -> dict[str, str]:
    """Parse '## [key] Heading' blocks out of the knowledge file."""
    try:
        text = CONTENT.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, str] = {}
    key, buf = None, []
    for line in text.splitlines():
        m = re.match(r"^##\s*\[([a-z_]+)\]\s*(.*)$", line)
        if m:
            if key:
                out[key] = "\n".join(buf).strip()
            key, buf = m.group(1), [f"### {m.group(2)}"]
        elif key:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf).strip()
    return out


def _cv() -> str:
    from app.services.guest_cv import cv_text
    return cv_text()


async def ask_about_tanishq(question: str = "", **ctx) -> dict:
    """Background, experience and how he works. The CV is the primary source."""
    s = _sections()
    cv = _cv()
    parts = []
    if cv:
        parts.append(f"### CV (authoritative — prefer this over anything below)\n{cv}")
    parts += [s.get("about", ""), s.get("freetime", ""), s.get("hiring", "")]
    body = "\n\n".join(p for p in parts if p)
    if not body:
        return {"error": "There's no profile or CV loaded yet."}
    return {
        "profile": body,
        "note": (
            "Answer only from this. Never invent an employer, date, grade or "
            "technology. If it isn't here, say you don't have it and offer to "
            "pass the question on."
        ),
    }


async def explain_project(name: str = "", **ctx) -> dict:
    """A real walkthrough, including the decisions and tradeoffs."""
    s = _sections()
    body = "\n\n".join(p for p in [s.get("kaia", ""), s.get("stack", "")] if p)
    return {"project": body or "Not written up yet."}


async def how_was_this_built(topic: str = "", **ctx) -> dict:
    """The architecture of the system the guest is currently talking to."""
    s = _sections()
    picks = {
        "documents": ["documents"], "sandbox": ["documents"], "rag": ["documents"],
        "voice": ["voice"], "audio": ["voice"], "speech": ["voice"],
        "safety": ["safety"], "security": ["safety"], "limits": ["safety"],
    }
    keys = picks.get((topic or "").lower().strip(), ["kaia", "documents", "voice", "safety", "stack"])
    body = "\n\n".join(s.get(k, "") for k in keys if s.get(k))
    return {"engineering": body or "Not written up yet."}


async def assess_fit(job_description: str = "", **ctx) -> dict:
    """Map a pasted JD against real experience — honestly, both ways."""
    if len(job_description.strip()) < 40:
        return {"error": "Paste the full job description and I'll go through it."}
    s = _sections()
    cv = _cv()
    evidence = "\n\n".join(
        p for p in (
            (f"### CV\n{cv}" if cv else ""),
            *(s.get(k, "") for k in ("about", "kaia", "documents", "voice", "safety", "stack")),
        ) if p
    )
    return {
        "job_description": job_description[:6000],
        "evidence": evidence,
        "instruction": (
            "Work through the JD requirement by requirement. For each, say whether "
            "there is concrete evidence in the material above, citing the specific "
            "thing he built. Where there is no evidence, say so plainly — do not "
            "stretch or infer. End with the honest gaps. A credible assessment is "
            "more use to a recruiter than a flattering one."
        ),
    }


async def get_code_sample(topic: str = "", **ctx) -> dict:
    """Show the real implementation of something they asked about."""
    samples = {
        "sandbox": ("backend/app/services/sandbox_runner.py", "Subprocess that runs pandas against an uploaded file"),
        "voice": ("backend/app/routes/voice.py", "Streaming STT/TTS over WebSockets"),
        "documents": ("backend/app/services/documents.py", "Storage, inspection and sandboxed analysis"),
        "export": ("backend/app/services/exporters.py", "Generating docx/pdf/xlsx"),
        "guest": ("backend/app/services/guest_passes.py", "The access-code system gating this portal"),
        "tools": ("backend/app/services/tool_registry.py", "How tools are registered and executed"),
    }
    key = (topic or "").lower().strip()
    match = next((v for k, v in samples.items() if k in key), None)
    if not match:
        return {"available": list(samples), "note": "Ask for one of these."}

    rel, desc = match
    path = REPO_ROOT / rel
    try:
        code = path.read_text(encoding="utf-8")[:6000]
    except OSError:
        return {"error": f"Couldn't read {rel}."}
    return {"file": rel, "describes": desc, "code": code}


async def send_cv(email: str = "", **ctx) -> dict:
    """Email the CV. Fixed template, and only to the address given."""
    addr = (email or "").strip()
    ok, why = valid_email(addr)
    if not ok:
        return {"error": why}

    s = get_settings()
    cv = Path(s.guest_cv_path) if getattr(s, "guest_cv_path", "") else None
    if not cv or not cv.is_file():
        return {"error": "The CV isn't uploaded yet — ask him to send it directly."}

    from app.services.guest_mail import send_cv_email
    ok, err = await send_cv_email(addr, cv)
    if not ok:
        return {"error": err}
    _log(ctx, "send_cv", addr)
    return {"sent_to": addr, "note": "Tell them it's on the way and to check spam."}


async def message_tanishq(name: str = "", email: str = "", message: str = "", **ctx) -> dict:
    """Relay a message to Tanishq. Goes to him, never from him."""
    if not message.strip():
        return {"error": "Nothing to send."}
    if email:
        ok, why = valid_email(email)
        if not ok:
            return {"error": why}

    from app.services.guest_mail import send_relay
    label = (ctx.get("pass_label") or "a visitor")
    ok, err = await send_relay(
        name=name.strip()[:80] or "Someone",
        reply_to=email.strip()[:120],
        body=message.strip()[:3000],
        via=label,
    )
    if not ok:
        return {"error": err}
    _log(ctx, "message_tanishq", f"{name} <{email}>")
    return {"delivered": True, "note": "Confirm it reached him and that he'll reply directly."}


async def analyse_upload(document_id: str = "", code: str = "", **ctx) -> dict:
    """Run pandas over a file the visitor uploaded.

    Always `untrusted=True`: the code is model-written on a public endpoint,
    so it runs as an unprivileged user that cannot read the server's secrets.
    """
    from app.services import documents as docs

    doc = None
    try:
        r = get_supabase().table("documents").select("*").eq("id", document_id).execute()
        doc = r.data[0] if r.data else None
    except Exception:
        pass
    if not doc:
        return {"error": "I can't find that file — ask them to upload it again."}

    if doc["kind"] != "table":
        text = docs.extract_text(docs.Path(doc["storage_path"]))
        return {"filename": doc["filename"], "content": text[:8000]}

    if not code.strip():
        probe = await docs.inspect_table(doc["storage_path"], untrusted=True)
        if not probe.get("ok"):
            return {"error": probe.get("error", "Couldn't read that file.")}
        return {"filename": doc["filename"], "schema": probe["output"]}

    result = await docs.run_analysis(doc["storage_path"], code, untrusted=True)
    if not result.get("ok"):
        return {"error": result.get("error"), "output": result.get("output", "")}
    if not result["output"].strip():
        return {"error": "The code ran but printed nothing. Print the value you want."}
    return {"result": result["output"]}


async def find_meeting_times(preferred_date: str = "", preferred_time: str = "", **ctx) -> dict:
    """Offer bookable slots. Never reveals what is already in his calendar."""
    from app.services.guest_booking import open_slots
    result = await open_slots(preferred_date, preferred_time)
    if not result.get("days"):
        return {"error": "Nothing free in the next week or so — leave a message instead."}
    result["note"] = (
        "These are the only times available. If 'requested' is present, it is the "
        "definitive answer about the time they asked for — use it rather than "
        "inferring from the list. Offer two or three options in plain language. "
        "Never claim a time is unavailable unless it is genuinely absent here."
    )
    return result


async def book_meeting(
    slot: str = "", email: str = "", name: str = "", note: str = "", **ctx
) -> dict:
    """Put a 30-minute meeting in his calendar with the guest invited."""
    ok, why = valid_email(email)
    if not ok:
        return {"error": why}
    if not slot.strip():
        return {"error": "Which slot? Call find_meeting_times first."}

    from app.services.guest_booking import book
    ok, err, when = await book(
        slot_id=slot,
        email=email.strip(),
        name=(name or "").strip()[:80],
        note=(note or "").strip()[:500],
        pass_label=ctx.get("pass_label") or "guest",
    )
    if not ok:
        return {"error": err}
    _log(ctx, "book_meeting", f"{email} {slot}")
    return {
        "booked": when,
        "note": "Confirm the time and tell them the invitation is in their inbox.",
    }


def _log(ctx: dict, kind: str, detail: str) -> None:
    pid = ctx.get("pass_id")
    if not pid:
        return
    try:
        get_supabase().table("guest_events").insert({
            "pass_id": pid, "kind": "tool", "detail": f"{kind}: {detail}"[:200],
        }).execute()
    except Exception:
        pass


def _register() -> None:
    guest_registry.register(ToolDef(
        name="ask_about_tanishq",
        description="Background, experience, how he works, and what he does outside work.",
        input_schema={
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
        executor=ask_about_tanishq, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="explain_project",
        description="A walkthrough of a project — what it does and the decisions behind it.",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "e.g. 'kaia'"}},
            "required": ["name"],
        },
        executor=explain_project, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="how_was_this_built",
        description=(
            "Explain the engineering of the assistant the visitor is using right now. "
            "Use this whenever they ask how it works, what the stack is, or about a "
            "specific part — pass a topic like 'voice', 'documents' or 'safety'."
        ),
        input_schema={
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "voice | documents | safety | stack"}},
        },
        executor=how_was_this_built, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="assess_fit",
        description=(
            "The visitor pastes a job description and gets an honest read on how "
            "Tanishq matches it, including where he doesn't. Use whenever they "
            "mention a role, vacancy or requirements."
        ),
        input_schema={
            "type": "object",
            "properties": {"job_description": {"type": "string"}},
            "required": ["job_description"],
        },
        executor=assess_fit, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="get_code_sample",
        description=(
            "Show real source code from the project for a topic they asked about. "
            "Topics: sandbox, voice, documents, export, guest, tools."
        ),
        input_schema={
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
        executor=get_code_sample, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="send_cv",
        description=(
            "Email Tanishq's CV to the visitor. Ask for their address first and "
            "repeat it back before sending. It only ever sends to that address."
        ),
        input_schema={
            "type": "object",
            "properties": {"email": {"type": "string", "description": "the visitor's own address"}},
            "required": ["email"],
        },
        executor=send_cv, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="analyse_upload",
        description=(
            "Work with a file the visitor uploaded. Call it with just the "
            "document_id first to see the real columns and sample rows, then "
            "again with pandas `code` to compute an answer.\n\n"
            "Never add up, average or count anything yourself from the sample "
            "rows — that is guessing. Write code and run it; only that returns "
            "the true figure. `df` is the table, `sheets` is every sheet by "
            "name, `pd` is pandas, and you only see what you print."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
                "code": {"type": "string", "description": "pandas that prints its result"},
            },
            "required": ["document_id"],
        },
        executor=analyse_upload, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="find_meeting_times",
        description=(
            "Get times the visitor can book with Tanishq. Call this whenever they "
            "ask to meet, talk, or set something up. If they named a day or a "
            "specific time, pass it — the result then says definitively whether "
            "that exact time is free, which you must use instead of guessing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "preferred_date": {"type": "string", "description": "YYYY-MM-DD if they named a day"},
                "preferred_time": {"type": "string", "description": "HH:MM 24h if they named a time, e.g. 15:00"},
            },
        },
        executor=find_meeting_times, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="book_meeting",
        description=(
            "Book a 30-minute meeting once they've picked a time. Pass the slot id "
            "from find_meeting_times exactly as given, plus their email and name. "
            "Google sends the calendar invitation automatically."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "slot": {"type": "string", "description": "slot id from find_meeting_times"},
                "email": {"type": "string", "description": "the visitor's address"},
                "name": {"type": "string"},
                "note": {"type": "string", "description": "what they want to discuss"},
            },
            "required": ["slot", "email"],
        },
        executor=book_meeting, category="guest",
    ))

    guest_registry.register(ToolDef(
        name="message_tanishq",
        description=(
            "Pass a message to Tanishq — interest in a role, a question, anything "
            "they want him to see. Collect their name and email so he can reply."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["message"],
        },
        executor=message_tanishq, category="guest",
    ))


_register()
