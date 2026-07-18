"""
Admin endpoints for managing the ClassifierEngine and system monitoring.

Provides:
  POST /admin/import-keywords — Import graded keywords from the Excel checklist
  GET  /admin/analytics     — System monitoring and analytics dashboard
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.models.event import Event
from app.models.schedule_item import ScheduleItem
from app.services.keyword_loader import load_keywords_from_excel, format_report
from app.services.classifier import load_graded_rules
from app.views.dashboard import _render  # Reuse Jinja2 rendering

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Expected location of the graded Excel file
EXCEL_PATH = Path(__file__).parent.parent.parent / "keywords_and_phrases_checklist.xlsx"


@router.post("/import-keywords")
async def import_keywords() -> Response:
    """
    Read the graded Excel checklist and update the ClassifierEngine rules.

    This triggers:
      1. Read keywords_and_phrases_checklist.xlsx
      2. Extract all Red/Yellow terms per trade
      3. Save to keywords_rules.json
      4. Reload rules into the ClassifierEngine (no restart needed)

    Returns a plain-text summary of what was imported.
    """
    if not EXCEL_PATH.exists():
        return Response(
            content=f"❌ Excel file not found: {EXCEL_PATH}\n"
                    "Please place the graded file at andon/keywords_and_phrases_checklist.xlsx",
            media_type="text/plain",
            status_code=404,
        )

    try:
        result = load_keywords_from_excel(str(EXCEL_PATH))
    except Exception as exc:
        logger.error("Failed to import keywords: %s", exc)
        return Response(
            content=f"❌ Import failed: {exc}",
            media_type="text/plain",
            status_code=500,
        )

    # Reload the rules into the classifier (no restart needed)
    load_graded_rules()

    report = format_report(result)
    logger.info("Keyword import complete:\n%s", report)
    return Response(content=report, media_type="text/plain")


# ── Pricing rates for cost estimation ──
DEFAULT_RATES = {
    "sms_per_segment": 0.0079,
    "mms_per_message": 0.02,
    "voice_per_minute": 0.013,
    "whisper_per_minute": 0.006,
    "storage_per_gb": 0.023,
}


@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics(
    request: Request,
    days: int = Query(30, alias="days"),
):
    """Render the admin analytics dashboard with usage, cost, and health metrics."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    today = date.today()

    async with async_session() as session:
        # Usage
        channel_counts = defaultdict(int)
        stmt = select(Event.channel, Event.direction, func.count().label("c")).where(
            Event.timestamp >= since).group_by(Event.channel, Event.direction)
        for row in (await session.execute(stmt)):
            channel_counts[row.channel] += row.c

        mms_stmt = select(func.count()).select_from(Event).where(
            Event.channel == "sms", Event.raw_payload.isnot(None), Event.timestamp >= since)
        mms_count = (await session.execute(mms_stmt)).scalar() or 0
        voice_stmt = select(func.count()).select_from(Event).where(
            Event.channel == "voice_message", Event.timestamp >= since)
        voice_count = (await session.execute(voice_stmt)).scalar() or 0
        total_stmt = select(func.count()).select_from(Event).where(Event.timestamp >= since)
        total_all = (await session.execute(total_stmt)).scalar() or 0

        usage = {
            "total_events": total_all, "sms": channel_counts.get("sms", 0),
            "email": channel_counts.get("email", 0), "voice": voice_count,
            "mms": mms_count, "voice_count": voice_count,
        }

        # Daily trends
        trends = []
        for i in range(min(days, 30)):
            ds = now - timedelta(days=(days - i - 1))
            de = ds + timedelta(days=1)
            d = {"date": ds.strftime("%b %d"), "sms": 0, "email": 0, "voice": 0}
            for row in (await session.execute(
                select(Event.channel, func.count().label("c")).where(
                    Event.timestamp >= ds, Event.timestamp < de).group_by(Event.channel))):
                if row.channel == "sms": d["sms"] = row.c
                elif row.channel == "email": d["email"] = row.c
                elif row.channel == "voice_message": d["voice"] = row.c
            trends.append(d)

        # Costs
        r = DEFAULT_RATES
        sms_cost = usage["sms"] * r["sms_per_segment"]
        mms_cost = usage["mms"] * r["mms_per_message"]
        voice_cost = usage["voice_count"] * r["voice_per_minute"]
        whisper_cost = usage["voice_count"] * r["whisper_per_minute"]
        total_cost = sms_cost + mms_cost + voice_cost + whisper_cost
        monthly_mult = 30.0 / days if days > 0 else 1.0
        costs = {
            "sms": round(sms_cost, 2), "mms": round(mms_cost, 2),
            "voice": round(voice_cost, 2), "whisper": round(whisper_cost, 2),
            "total_current": round(total_cost, 2),
            "monthly_projected": round(total_cost * monthly_mult, 2),
        }

        # Issue insights
        red = (await session.execute(
            select(func.count()).select_from(Event).where(
                Event.outcome == "R", Event.timestamp >= since))).scalar() or 0
        yellow = (await session.execute(
            select(func.count()).select_from(Event).where(
                Event.outcome == "Y", Event.timestamp >= since))).scalar() or 0
        corr = (await session.execute(
            select(func.count()).select_from(Event).where(
                Event.full_text.like("[CLASSIFICATION CORRECTION]%"),
                Event.timestamp >= since))).scalar() or 0
        total_cls = red + yellow
        issues = {
            "red": red, "yellow": yellow,
            "corrections": corr,
            "correction_rate": round(corr / total_cls * 100, 1) if total_cls > 0 else 0,
        }

        # Trade breakdown
        trade_rows = (await session.execute(
            select(Event.trade, func.count().label("c")).where(
                Event.outcome.isnot(None), Event.trade.isnot(None), Event.trade != "",
                Event.timestamp >= since).group_by(Event.trade).order_by(desc("c")).limit(10)))
        trade_breakdown = [{"trade": r.trade, "count": r.c} for r in trade_rows]

        # Top subs
        sub_rows = (await session.execute(
            select(Event.sender_phone, func.count().label("c")).where(
                Event.outcome.isnot(None), Event.timestamp >= since,
                Event.sender_phone.isnot(None)).group_by(Event.sender_phone)
            .order_by(desc("c")).limit(10)))
        top_subs = [{"sender": r.sender_phone, "count": r.c} for r in sub_rows]

        # System health
        media_evt = (await session.execute(
            select(func.count()).select_from(Event).where(
                Event.raw_payload.isnot(None), Event.timestamp >= since))).scalar() or 0
        sched_cnt = (await session.execute(
            select(func.count()).select_from(ScheduleItem))).scalar() or 0
        health = {
            "total_schedules": sched_cnt, "media_events": media_evt,
            "error_count": 0, "avg_resolution_hours": None,
        }

    html = _render("admin/analytics.html",
        request=request, days=days, usage=usage, usage_trends=trends,
        costs=costs, issues=issues, trade_breakdown=trade_breakdown,
        top_subs=top_subs, health=health, today=today, rates=DEFAULT_RATES,
    )
    return HTMLResponse(html)
