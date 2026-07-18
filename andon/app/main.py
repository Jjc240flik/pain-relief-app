"""
Main application entry point for the SMS Andon System.

Run with: uvicorn app.main:app --reload
"""

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.webhooks.twilio import router as twilio_router
from app.api import router as api_router
from app.api.seed import router as seed_router
from app.api.schedule import router as schedule_router
from app.services.scheduler import SchedulerService

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

_scheduler = SchedulerService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the APScheduler on startup, shut down on teardown."""
    logger.info("Starting SMS Andon System...")
    _scheduler.start()
    yield
    _scheduler.stop()
    logger.info("SMS Andon System shut down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SMS Andon System",
    description="Multi-channel status tracking for home builders (TLG Homes)",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow all origins for MVP (dashboard served separately)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

app.include_router(api_router)       # /api/health
app.include_router(seed_router)      # /api/seed
app.include_router(schedule_router)  # /api/schedule
app.include_router(twilio_router)    # /webhooks/twilio/*
