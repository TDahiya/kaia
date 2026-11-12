"""Let a guest book time with Tanishq.

Slots come from fixed windows defined here, not from reading his calendar —
a visitor should never learn what is in it. His real free/busy is checked
server-side only, to avoid double-booking, and the result is never exposed:
a busy slot is simply absent from the list.
"""

import logging
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from app.database import get_supabase
from app.services.google_auth import get_google_credentials

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Dublin")

# When he's bookable. Weekdays only; 0 = Monday.
WORK_DAYS = {0, 1, 2, 3, 4}
DAY_START = dtime(10, 0)
DAY_END = dtime(17, 30)
SLOT_MINUTES = 30

# How far ahead, and the minimum notice so nothing lands in 10 minutes.
MAX_DAYS_AHEAD = 10
MIN_NOTICE_HOURS = 2

# Days returned when no particular day was asked for. Slots are never
# truncated within a day — doing that made the model report a time as
# unavailable when it had simply been cut off the end of the list.
DEFAULT_DAYS_SHOWN = 2


async def _service():
    db = get_supabase()
    row = db.table("integrations").select("user_id, org_id") \
        .eq("provider", "google").eq("status", "active").execute()
    if not row.data:
        return None
    creds = await get_google_credentials(row.data[0]["user_id"], row.data[0]["org_id"])
    if not creds:
        return None
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _candidate_slots(now: datetime) -> list[datetime]:
    out: list[datetime] = []
    earliest = now + timedelta(hours=MIN_NOTICE_HOURS)
    day = now.date()
    for offset in range(MAX_DAYS_AHEAD + 1):
        d = day + timedelta(days=offset)
        if d.weekday() not in WORK_DAYS:
            continue
        cursor = datetime.combine(d, DAY_START, tzinfo=TZ)
        end = datetime.combine(d, DAY_END, tzinfo=TZ)
        while cursor <= end:
            if cursor >= earliest:
                out.append(cursor)
            cursor += timedelta(minutes=SLOT_MINUTES)
    return out


async def _busy_ranges(svc, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    try:
        res = svc.freebusy().query(body={
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": "primary"}],
        }).execute()
    except Exception:
        logger.exception("booking: freebusy failed")
        return []
    out = []
    for b in res.get("calendars", {}).get("primary", {}).get("busy", []):
        try:
            out.append((
                datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                datetime.fromisoformat(b["end"].replace("Z", "+00:00")),
            ))
        except Exception:
            continue
    return out


def _fmt(s: datetime) -> dict:
    return {"id": s.strftime("%Y-%m-%dT%H:%M"), "time": s.strftime("%H:%M")}


async def open_slots(preferred_date: str = "", preferred_time: str = "") -> dict:
    """Bookable slots, his real commitments quietly removed.

    A requested day is answered in full so the model can see every time that
    day, and the specific time asked for is reported explicitly — otherwise
    it infers "unavailable" from a list that was merely cut short.
    """
    now = datetime.now(TZ)
    candidates = _candidate_slots(now)
    if not candidates:
        return {"days": [], "note": "Nothing bookable in the next week or so."}

    svc = await _service()
    busy: list[tuple[datetime, datetime]] = []
    if svc:
        busy = await _busy_ranges(svc, candidates[0], candidates[-1] + timedelta(minutes=SLOT_MINUTES))

    def is_free(s: datetime) -> bool:
        finish = s + timedelta(minutes=SLOT_MINUTES)
        return not any(s < b_end and finish > b_start for b_start, b_end in busy)

    free = [s for s in candidates if is_free(s)]

    # Group by day, preserving order.
    by_day: dict[str, list[datetime]] = {}
    for s in free:
        by_day.setdefault(s.strftime("%Y-%m-%d"), []).append(s)

    wanted_day = (preferred_date or "").strip()
    result: dict = {}

    if wanted_day and wanted_day in by_day:
        days = [wanted_day]
    elif wanted_day:
        # Asked for a day with nothing on it — say so rather than silently
        # answering about a different day.
        result["requested_day_unavailable"] = wanted_day
        days = list(by_day)[:DEFAULT_DAYS_SHOWN]
    else:
        days = list(by_day)[:DEFAULT_DAYS_SHOWN]

    result["days"] = [
        {
            "date": d,
            "label": datetime.strptime(d, "%Y-%m-%d").strftime("%A %d %B"),
            "slots": [_fmt(s) for s in by_day[d]],
        }
        for d in days
    ]

    # Answer the exact time directly, so it never has to be inferred.
    wanted_time = (preferred_time or "").strip()
    if wanted_day and wanted_time:
        target = f"{wanted_day}T{wanted_time}"
        exact = next((s for s in free if s.strftime("%Y-%m-%dT%H:%M") == target), None)
        result["requested"] = {
            "slot": target,
            "available": exact is not None,
            "reason": "" if exact else (
                "That exact time isn't bookable — it's either outside 10:00–17:30, "
                "not on the half hour, too soon, or already taken."
            ),
        }

    result["timezone"] = "Europe/Dublin"
    result["hours"] = "Weekdays 10:00–17:30, 30-minute slots"
    return result


def parse_slot(slot_id: str) -> datetime | None:
    try:
        naive = datetime.strptime(slot_id.strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    start = naive.replace(tzinfo=TZ)

    now = datetime.now(TZ)
    if start < now + timedelta(hours=MIN_NOTICE_HOURS):
        return None
    if start > now + timedelta(days=MAX_DAYS_AHEAD + 1):
        return None
    if start.weekday() not in WORK_DAYS:
        return None
    if not (DAY_START <= start.time() <= DAY_END):
        return None
    if start.minute % SLOT_MINUTES:
        return None
    return start


async def book(slot_id: str, email: str, name: str, note: str, pass_label: str) -> tuple[bool, str, str]:
    """Create the event. Returns (ok, message, human_time)."""
    start = parse_slot(slot_id)
    if not start:
        return False, "That time isn't one of the available slots.", ""

    svc = await _service()
    if not svc:
        return False, "His calendar isn't connected right now, so I can't book it.", ""

    finish = start + timedelta(minutes=SLOT_MINUTES)

    # Re-check immediately before writing, in case it went in the meantime.
    busy = await _busy_ranges(svc, start, finish)
    if any(start < b_end and finish > b_start for b_start, b_end in busy):
        return False, "That slot just got taken — pick another.", ""

    body = {
        "summary": f"Kaia intro — {name or 'guest'}",
        "description": (
            f"Booked through the Kaia guest portal.\n\n"
            f"Name: {name or '(not given)'}\n"
            f"Email: {email}\n"
            f"Pass: {pass_label}\n"
            f"\n{note or ''}"
        ).strip(),
        "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Dublin"},
        "end": {"dateTime": finish.isoformat(), "timeZone": "Europe/Dublin"},
        "attendees": [{"email": email}],
        "reminders": {"useDefault": True},
    }

    try:
        svc.events().insert(
            calendarId="primary", body=body, sendUpdates="all",
        ).execute()
    except Exception as e:
        logger.exception("booking: insert failed")
        return False, f"That didn't go through — {type(e).__name__}.", ""

    human = start.strftime("%A %d %B at %H:%M") + " (Irish time)"
    return True, "", human


def _demo() -> None:
    now = datetime.now(TZ)
    slots = _candidate_slots(now)
    assert slots, "no candidate slots"
    for s in slots:
        assert s.weekday() in WORK_DAYS
        assert DAY_START <= s.time() <= DAY_END
        assert s >= now + timedelta(hours=MIN_NOTICE_HOURS) - timedelta(seconds=1)

    # Out-of-window and past times are rejected.
    assert parse_slot("2020-01-01T10:00") is None       # past
    assert parse_slot("not-a-time") is None
    soon = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
    assert parse_slot(soon) is None, "accepted a slot inside the notice period"

    good = slots[0].strftime("%Y-%m-%dT%H:%M")
    assert parse_slot(good) is not None, f"rejected its own slot {good}"
    print(f"ok — {len(slots)} candidate slots, first {good}")


if __name__ == "__main__":
    _demo()
