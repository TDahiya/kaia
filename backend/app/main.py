"""Kaia AI Assistant — FastAPI backend."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import get_settings

# Import tool modules to register them
import app.services.tools.weather  # noqa: F401
import app.services.tools.memory_tools  # noqa: F401
import app.services.tools.google_calendar  # noqa: F401
import app.services.tools.google_gmail  # noqa: F401
import app.services.tools.google_sheets_crm  # noqa: F401
import app.services.tools.phone_tools  # noqa: F401
import app.services.tools.google_maps  # noqa: F401

from app.routes import chat, agents, integrations, usage, memories, voice, telephony, health

scheduler = AsyncIOScheduler()


async def weekly_summary_job():
    """Scheduled weekly memory summarization."""
    from app.database import get_supabase
    from app.services.memory_summarizer import run_weekly_summary
    db = get_supabase()
    users = db.table("users").select("id, org_id").execute()
    for u in users.data:
        try:
            await run_weekly_summary(u["id"], u["org_id"])
        except Exception as e:
            print(f"Weekly summary failed for user {u['id']}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schedule weekly summary: Sundays at 3am
    scheduler.add_job(weekly_summary_job, "cron", day_of_week="sun", hour=3)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Kaia AI Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[s.app_base_url, "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(agents.router)
app.include_router(integrations.router)
app.include_router(usage.router)
app.include_router(memories.router)
app.include_router(voice.router)
app.include_router(telephony.router)
