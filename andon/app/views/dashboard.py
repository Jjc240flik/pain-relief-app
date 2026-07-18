"""
Dashboard routes — Daily Red/Yellow view with HTMX actions.
Uses raw Jinja2 directly (not starlette's Jinja2Templates wrapper) for reliability.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import jinja2
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.house import House
from app.models.schedule_item import ScheduleItem
from app.models.event import Event
from app.models.contact import Contact
from app.repositories.schedule_repo import ScheduleRepository
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["dashboard"])

# ---------------------------------------------------------------------------
# Jinja2 environment (manual setup — avoids starlette wrapper compatibility)
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_loader = jinja2.FileSystemLoader(str(_TEMPLATE_DIR))
_env = jinja2.Environment(loader=_loader, autoescape=True)


def _render(name: str, **context) -> str:
    """Render a Jinja2 template with the given context."""
    template = _env.get_template(name)
    return template.render(**context)


# ---------------------------------------------------------------------------
# Trade display names
# ---------------------------------------------------------------------------

TRADE_LABELS = {
    "foundation_concrete": "Foundation / Concrete",
    "framing": "Framing",
    "plumbing_rough": "Plumbing Rough",
    "hvac_rough": "HVAC Rough",
    "electrical_rough": "Electrical Rough",
    "drywall_plaster": "Drywall / Plaster",
    "paint": "Paint",
    "flooring": "Flooring",
    "cabinets": "Cabinets",
    "finish_work": "Finish Work",
}

TRADE_NOTES = {
    "foundation_concrete": "Extra midpoint checks active",
    "framing": "Selective escalation active",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _time_ago(dt: datetime | None) -> str | None:
    """Human-readable time since last touch."""
    if not dt:
        return None
    now = datetime.now(timezone.utc) if dt.tzinfo else datetime.now()
    diff = now - dt
    if diff.total_seconds() < 60:
        return "just now"
    if diff.total_seconds() < 3600:
        mins = int(diff.total_seconds() / 60)
        return f"{mins}m ago"
    if diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours}h ago"
    days = diff.days
    return f"{days}d ago"


async def _get_red_yellow_items(session: AsyncSession) -> list[dict]:
    """Query all schedule items with R or Y status, joined with houses and latest event."""
    stmt = (
        select(ScheduleItem)
        .options(selectinload(ScheduleItem.house))
        .where(ScheduleItem.andon_status.in_(["R", "Y"]))
        .order_by(desc(ScheduleItem.last_touch_ts))
    )
    result = await session.execute(stmt)
    items = result.scalars().all()

    rows = []
    for item in items:
        house = item.house
        if not house:
            continue

        # Get the latest inbound event for this schedule item
        event_stmt = (
            select(Event)
            .where(
                Event.schedule_item_id == item.id,
                Event.direction == "inbound",
            )
            .order_by(desc(Event.timestamp))
            .limit(1)
        )
        event_result = await session.execute(event_stmt)
        latest_event = event_result.scalar_one_or_none()

        # Get the subcontractor contact info for this trade
        _sub_name, _sub_phone = await _get_sub_contact(session, item.trade)

        rows.append({
            "id": str(item.id),
            "house_id": str(item.house_id),
            "address": house.address,
            "trade": item.trade,
            "trade_display": TRADE_LABELS.get(item.trade, item.trade.replace("_", " ").title()),
            "trade_note": TRADE_NOTES.get(item.trade),
            "andon_status": item.andon_status,
            "last_message": latest_event.full_text if latest_event else None,
            "last_touch_ts": item.last_touch_ts,
            "time_ago": _time_ago(item.last_touch_ts),
            "scheduled_start": item.scheduled_start,
            "sub_name": _sub_name,
            "sub_phone": _sub_phone,
        })

    return rows


async def _get_sub_contact(session: AsyncSession, trade: str) -> tuple[str | None, str | None]:
    """Look up the subcontractor name and phone for a given trade."""
    if not trade:
        return None, None
    stmt = select(Contact).where(
        Contact.trade == trade,
        Contact.is_active == True,  # noqa: E712
    ).limit(1)
    result = await session.execute(stmt)
    contact = result.scalar_one_or_none()
    if contact:
        return contact.name, contact.phone
    return None, None


async def _log_action(
    session: AsyncSession,
    item_id: UUID,
    action: str,
    detail: str | None = None,
) -> None:
    """Log a dashboard action as an immutable Event record."""
    repo = ScheduleRepository(session)
    item = await repo.get(item_id)
    if not item:
        return

    event_repo = BaseRepository(session, Event)
    text = f"[DASHBOARD] {action}"
    if detail:
        text += f": {detail}"

    await event_repo.create(
        direction="outbound",
        channel="sms",
        full_text=text,
        house_id=item.house_id,
        schedule_item_id=item.id,
        trade=item.trade,
        triggered_by="pm",
    )


async def _render_rows(session: AsyncSession) -> str:
    """Render just the house rows partial."""
    items = await _get_red_yellow_items(session)
    return _render("partials/house_rows.html", items=items)

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, session: AsyncSession = Depends(get_db)):
    """Render the full dashboard page."""
    items = await _get_red_yellow_items(session)
    today = date.today().strftime("%B %d, %Y")
    red_count = sum(1 for i in items if i["andon_status"] == "R")
    yellow_count = sum(1 for i in items if i["andon_status"] == "Y")

    html = _render(
        "dashboard.html",
        items=items,
        today=today,
        red_count=red_count,
        yellow_count=yellow_count,
    )
    return HTMLResponse(html)


@router.get("/dashboard/partial", response_class=HTMLResponse)
async def dashboard_partial(request: Request, session: AsyncSession = Depends(get_db)):
    """HTMX partial — returns only the house_rows partial."""
    html = await _render_rows(session)
    return HTMLResponse(html)


@router.post("/dashboard/{item_id}/resolve")
async def resolve_item(
    request: Request,
    item_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Resolve: set andon_status to Green, log event, return updated row list."""
    repo = ScheduleRepository(session)
    await repo.update(item_id, andon_status="G")
    await _log_action(session, item_id, "Resolved", "Status set to Green")
    await session.commit()

    html = await _render_rows(session)
    return HTMLResponse(html)


@router.post("/dashboard/{item_id}/push")
async def push_item(
    request: Request,
    item_id: UUID,
    days: int = Query(1),
    session: AsyncSession = Depends(get_db),
):
    """Push schedule dates by N days, log event, return updated row list."""
    repo = ScheduleRepository(session)
    item = await repo.get(item_id)
    if not item:
        return HTMLResponse("", status_code=404)

    updates = {}
    if item.scheduled_start:
        updates["scheduled_start"] = item.scheduled_start + timedelta(days=days)
    if item.scheduled_end:
        updates["scheduled_end"] = item.scheduled_end + timedelta(days=days)

    if updates:
        await repo.update(item_id, **updates)

    await _log_action(session, item_id, f"Push +{days} day(s)")
    await session.commit()

    html = await _render_rows(session)
    return HTMLResponse(html)


@router.post("/dashboard/{item_id}/push-custom")
async def push_custom_item(
    request: Request,
    item_id: UUID,
    new_start_date: str = Form(...),
    session: AsyncSession = Depends(get_db),
):
    """Push schedule to a specific date, log event, return updated row list."""
    repo = ScheduleRepository(session)
    item = await repo.get(item_id)
    if not item:
        return HTMLResponse("", status_code=404)

    try:
        parsed = date.fromisoformat(new_start_date)
    except ValueError:
        return HTMLResponse("Invalid date", status_code=400)

    if item.scheduled_start:
        days_diff = (parsed - item.scheduled_start).days
        updates = {"scheduled_start": parsed}
        if item.scheduled_end:
            updates["scheduled_end"] = item.scheduled_end + timedelta(days=days_diff)

        await repo.update(item_id, **updates)
        await _log_action(session, item_id, f"Custom date push", f"New start: {parsed}")
        await session.commit()

    html = await _render_rows(session)
    return HTMLResponse(html)


@router.post("/dashboard/{item_id}/escalate")
async def escalate_item(
    request: Request,
    item_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Escalate to owner — log a specific event, no status change."""
    await _log_action(session, item_id, "Escalated to owner")
    await session.commit()

    html = await _render_rows(session)
    return HTMLResponse(html)
