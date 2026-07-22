"""
Dashboard routes — Daily Red/Yellow view with HTMX actions.
Uses raw Jinja2 directly (not starlette's Jinja2Templates wrapper) for reliability.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

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
from app.services.auth import require_admin, optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["dashboard"], dependencies=[Depends(require_admin)])

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

# Build phase order — matching seed.py
TRADE_PHASES = [
    "foundation_concrete", "framing", "plumbing_rough", "hvac_rough",
    "electrical_rough", "drywall_plaster", "paint", "flooring",
    "cabinets", "finish_work",
]

TRADE_NOTES = {}


# ── Cascade push helpers ──

def _get_following_trades(trade: str) -> list[str]:
    """Return trades that come after the given trade in build order."""
    try:
        idx = TRADE_PHASES.index(trade)
        return TRADE_PHASES[idx + 1:]
    except ValueError:
        return []


async def _get_following_trade_items(
    session: AsyncSession, house_id, trade: str,
) -> list[ScheduleItem]:
    """Get schedule items for trades that follow the given trade for a house, ordered by phase."""
    following = _get_following_trades(trade)
    if not following:
        return []
    stmt = (
        select(ScheduleItem)
        .where(
            ScheduleItem.house_id == house_id,
            ScheduleItem.trade.in_(following),
        )
        .order_by(ScheduleItem.scheduled_start)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())
    # Sort by phase order
    items.sort(key=lambda si: TRADE_PHASES.index(si.trade) if si.trade in TRADE_PHASES else 999)
    return items


def _build_push_updates(item: ScheduleItem, days: int) -> dict:
    """Build the update dict for pushing a schedule item by N days."""
    updates = {}
    if item.scheduled_start:
        updates["scheduled_start"] = item.scheduled_start + timedelta(days=days)
    if item.scheduled_end:
        updates["scheduled_end"] = item.scheduled_end + timedelta(days=days)
    return updates


# ── Contextual quick actions per trade ──
CONTEXTUAL_ACTIONS = {
    "framing": [
        {"label": "Call Supplier", "icon": "📞", "action": "call_contact"},
        {"label": "Request Inspection", "icon": "🔍", "action": "prefill_note", "message": "Schedule framing inspection at {address} — ready for review."},
    ],
    "finish_work": [
        {"label": "Review Punch List", "icon": "📝", "action": "prefill_note", "message": "Review final punch list items at {address} before sign-off."},
        {"label": "Schedule Walkthrough", "icon": "👁", "action": "prefill_note", "message": "Schedule final walkthrough at {address} with owner."},
    ],
}

# Cleanliness / blocking actions (shown when message contains cleanliness or blocking keywords)
CONTEXTUAL_ACTIONS["_cleanliness"] = [
    {"label": "Flag for Cleanup", "icon": "🧹", "action": "prefill_note", "message": "Site cleanup needed at {address} before next trade can start."},
    {"label": "Notify Next Trade", "icon": "📢", "action": "prefill_note", "message": "Notify next trade that cleanup is in progress at {address} — expect delay."},
]


def _get_contextual_actions(trade: str, last_message: str | None) -> list[dict]:
    """Return 2-3 contextual actions for a card based on trade and message content."""
    actions = []
    msg = (last_message or "").lower()

    # Check for cleanliness/blocking keywords
    if any(kw in msg for kw in ("clean", "debris", "trash", "mess", "blocking", "cannot start")):
        actions.extend(CONTEXTUAL_ACTIONS.get("_cleanliness", []))

    # Add trade-specific actions (up to 2)
    trade_actions = CONTEXTUAL_ACTIONS.get(trade, [])
    actions.extend(trade_actions[:2])

    # If no contextual actions found, return empty list (no extras shown)
    return actions[:3]


# ═══════════════════════════════════════════════════════════════
# RENDERING HELPERS
# ═══════════════════════════════════════════════════════════════

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


def _last_activity_label(latest_event, last_touch_ts, behind_verified=True):
    """Derive a human-readable 'Last Verified' label from the latest event.

    Maps structured replies to descriptive activity indicators:
      "1"/"yes"                       → ✓ Onsite HH:MM
      "done"/"complete"/"a"           → ✓ Completed HH:MM
      "2"/"no"/"partial" (verified)   → ⚠ Behind HH:MM
      "2"/"no"/"partial" (unverified) → ⚠ Unconfirmed HH:MM
      "3"/"issue..."                  → 🔴 Issue Reported HH:MM
      "b"/"not clean"                 → ⚠ Unclean HH:MM
      No reply after check-in         → ⏳ Response Pending since HH:MM
      Free-form message               → 📝 Message Received HH:MM
      No event, but touch exists      → Updated HH:MM
    """
    if not latest_event and not last_touch_ts:
        return None
    ts = latest_event.timestamp if latest_event else last_touch_ts
    time_str = ts.strftime("%-I:%M %p").lower() if hasattr(ts, 'strftime') else ""

    # No event data — just a timestamp update
    if not latest_event or not latest_event.full_text:
        if not time_str:
            return None
        return f"Updated {time_str}"

    text = latest_event.full_text.strip().lower()

    # Onsite confirmation (sub confirmed arrival/readiness)
    if text in ("1", "yes"):
        return f"✓ Onsite {time_str}" if time_str else "✓ Onsite"

    # Completion confirmation
    if text in ("done", "complete", "a"):
        return f"✓ Completed {time_str}" if time_str else "✓ Completed"

    # Cleanliness confirmation
    if text in ("clean",):
        return f"✓ Clean {time_str}" if time_str else "✓ Clean"

    # Behind / delayed (with or without verification)
    if text in ("2", "no", "partial"):
        if behind_verified:
            return f"⚠ Behind {time_str}" if time_str else "⚠ Behind"
        else:
            return f"⚠ Unconfirmed {time_str}" if time_str else "⚠ Unconfirmed"

    # Issue reported
    if text in ("3",) or text.startswith("issue"):
        return f"🔴 Issue Reported {time_str}" if time_str else "🔴 Issue Reported"

    # Site unclean
    if text in ("b", "not clean"):
        return f"⚠ Unclean {time_str}" if time_str else "⚠ Unclean"

    # Not ready
    if text.startswith("not ready"):
        return f"🔴 Not ready {time_str}" if time_str else "🔴 Not ready"

    # Catch-all for free-form messages
    return f"📝 Message Received {time_str}" if time_str else "📝 Message Received"


def _parse_media_info(latest_event) -> list[dict]:
    """Extract media attachment info from an event's raw_payload."""
    if not latest_event or not latest_event.raw_payload:
        return []
    raw = latest_event.raw_payload
    if isinstance(raw, dict):
        media = raw.get("media")
        if isinstance(media, list):
            return media
    return []


def _count_media_by_type(latest_event, category: str) -> int:
    """Count media attachments of a specific category (photo/video)."""
    return sum(
        1 for m in _parse_media_info(latest_event)
        if m.get("category") == category
    )


async def _get_red_yellow_items(session: AsyncSession, filter_status: str | None = None) -> list[dict]:
    """Query schedule items with R or Y status, optionally filtered to one status.
    
    When filter_status is 'R' or 'Y', only items with that status are returned.
    When None, all R and Y items are returned.
    """
    statuses = ["R", "Y"]
    if filter_status in ("R", "Y"):
        statuses = [filter_status]
    
    stmt = (
        select(ScheduleItem)
        .options(selectinload(ScheduleItem.house))
        .where(ScheduleItem.andon_status.in_(statuses))
        .order_by(ScheduleItem.last_touch_ts.asc().nullslast())
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

        # Collect media from ALL recent inbound events for this item
        # (not just the latest — media may be in an older MMS event)
        all_events_stmt = (
            select(Event)
            .where(
                Event.schedule_item_id == item.id,
                Event.direction == "inbound",
                Event.raw_payload.isnot(None),
            )
            .order_by(desc(Event.timestamp))
            .limit(20)
        )
        all_result = await session.execute(all_events_stmt)
        all_events = all_result.scalars().all()
        all_media = []
        for evt in all_events:
            all_media.extend(_parse_media_info(evt))

        # Get the subcontractor contact info for this trade
        _sub_name, _sub_phone, _sub_email, _boss_phone = await _get_sub_contact(session, item.trade)

        # ── Evaluate "Behind" status (Option B + C) ──
        is_behind, behind_verified = await _evaluate_behind_status(session, item, _sub_name)

        rows.append({
            "id": str(item.id),
            "house_id": str(item.house_id),
            "address": house.address,
            "city": house.city or "",
            "trade": item.trade,
            "trade_display": TRADE_LABELS.get(item.trade, item.trade.replace("_", " ").title()),
            "trade_note": TRADE_NOTES.get(item.trade),
            "andon_status": item.andon_status,
            "last_message": latest_event.full_text if latest_event else None,
            "last_touch_ts": item.last_touch_ts,
            "time_ago": _time_ago(item.last_touch_ts),
            "activity_label": _last_activity_label(latest_event, item.last_touch_ts, behind_verified),
            "scheduled_start": item.scheduled_start,
            "sub_name": _sub_name,
            "sub_phone": _sub_phone,
            "sub_email": _sub_email,
            "boss_phone": _boss_phone,
            # ── Delegation info ──
            "delegated_to": item.delegated_to or "",
            "delegated_by": item.delegated_by or "",
            "delegation_note": item.delegation_note or "",
            "delegation_status": item.delegation_status or "",
            # ── Contextual quick actions based on trade + message ──
            "contextual_actions": _get_contextual_actions(item.trade, latest_event.full_text if latest_event else None),
            # ── Following trades for cascade push (same house, later phases) ──
            "following_trades": _get_following_trades(item.trade),
            # ── Media attachments from ALL recent events (MMS photos/video) ──
            "media_info": all_media,
            "photo_count": sum(1 for m in all_media if m.get("category") == "photo"),
            "has_video": any(m.get("category") == "video" for m in all_media),
            "media_list": all_media,
        })

    return rows


async def _get_sub_contact(session: AsyncSession, trade: str) -> tuple:
    """Look up the subcontractor name, phone, email, and manager phone for a given trade."""
    if not trade:
        return None, None, None, None
    stmt = select(Contact).where(
        Contact.trade == trade,
        Contact.is_active == True,  # noqa: E712
    ).limit(1)
    result = await session.execute(stmt)
    contact = result.scalar_one_or_none()
    if contact:
        return contact.name, contact.phone, contact.email, contact.manager_phone
    return None, None, None, None


# ── Option C threshold: contacts with this many "Behind" marks ──
HIGH_RISK_THRESHOLD = 3


async def _evaluate_behind_status(
    session: AsyncSession,
    schedule_item,
    sub_name: str | None,
) -> tuple[bool, bool]:
    """
    Evaluate whether a schedule item should be flagged as "Behind".

    Implements Option B (Primary Rule) + Option C (History-Based):
    -----------------------------------------------------------------
    Option B — Only mark "Behind" if:
      1. The scheduled start time has passed, AND
      2. We actually sent a proactive check-in message
         (Readiness Check or Day-Before Confirmation), AND
      3. The sub either didn't reply, or replied negatively ("2"/"no"/"partial")

    Option C — If a contact has been marked "Behind" more than
    HIGH_RISK_THRESHOLD times in the past, apply stricter criteria.
    """
    from datetime import date as dt_date
    if not schedule_item.scheduled_start or schedule_item.scheduled_start > dt_date.today():
        return False, False

    # ── Check if we sent a proactive check-in ──
    # First try: same schedule_item_id
    checkin_stmt = (
        select(Event)
        .where(
            Event.schedule_item_id == schedule_item.id,
            Event.direction == "outbound",
            Event.channel == "sms",
            Event.full_text.like("TLG –%"),
        )
        .order_by(desc(Event.timestamp))
        .limit(1)
    )
    checkin_result = await session.execute(checkin_stmt)
    latest_checkin = checkin_result.scalar_one_or_none()

    # Second try: check by trade + sender phone combination.
    # Use any recent outbound check-in for this trade regardless of house.
    if not latest_checkin:
        checkin_stmt2 = (
            select(Event)
            .where(
                Event.direction == "outbound",
                Event.channel == "sms",
                Event.full_text.like("TLG –%"),
                Event.trade == schedule_item.trade,
            )
            .order_by(desc(Event.timestamp))
            .limit(1)
        )
        checkin_result2 = await session.execute(checkin_stmt2)
        latest_checkin = checkin_result2.scalar_one_or_none()

    sent_checkin = latest_checkin is not None

    # ── Get the last inbound reply after the check-in ──
    last_reply = None
    if sent_checkin:
        reply_stmt = (
            select(Event)
            .where(
                Event.schedule_item_id == schedule_item.id,
                Event.direction == "inbound",
                Event.timestamp > latest_checkin.timestamp,
            )
            .order_by(desc(Event.timestamp))
            .limit(1)
        )
        reply_result = await session.execute(reply_stmt)
        last_reply = reply_result.scalar_one_or_none()

    # ── Option C: estimate contact's behind history from events ──
    behind_count = 0
    if sub_name:
        behind_stmt = (
            select(Event)
            .where(
                Event.full_text.like("%Behind%"),
                Event.direction == "outbound",
            )
        )
        behind_events = await session.execute(behind_stmt)
        behind_count = len(list(behind_events.scalars().all()))
    is_high_risk = behind_count >= HIGH_RISK_THRESHOLD

    # ── Apply Option B logic ──
    if sent_checkin and last_reply:
        reply_text = (last_reply.full_text or "").strip().lower()
        if reply_text in ("1", "yes", "done", "complete", "clean", "a"):
            return False, True
        elif reply_text in ("2", "no", "partial"):
            return True, True
        elif reply_text in ("3",) or reply_text.startswith("issue"):
            return False, True
        else:
            return False, True
    elif sent_checkin and not last_reply:
        return True, True
    else:
        if is_high_risk:
            return True, False
        return False, False


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


async def _render_rows(session: AsyncSession, filter_status: str | None = None) -> str:
    """Render just the house rows partial, optionally filtered by status (R or Y)."""
    items = await _get_red_yellow_items(session, filter_status)
    return _render("partials/house_rows.html", items=items)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
    filter: str = Query("", alias="f"),
):
    """Render the full dashboard page."""
    items = await _get_red_yellow_items(session, filter or None)
    today = date.today().strftime("%B %d, %Y")
    red_count = sum(1 for i in items if i["andon_status"] == "R")
    yellow_count = sum(1 for i in items if i["andon_status"] == "Y")

    # Get company name
    from sqlalchemy import text as sql_text
    result = await session.execute(sql_text("SELECT value FROM tenant_settings WHERE key = 'company_name'"))
    row = result.fetchone()
    company_name = row[0] if row else "TLG Andon"

    html = _render(
        "dashboard.html",
        items=items,
        today=today,
        red_count=red_count,
        yellow_count=yellow_count,
        company_name=company_name,
        user=user,
        active_filter=filter or "",
    )
    return HTMLResponse(html)


@router.get("/dashboard/partial", response_class=HTMLResponse)
async def dashboard_partial(
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
    filter: str = Query("", alias="f"),
):
    """HTMX partial — returns the house rows partial, optionally filtered."""
    rows_html = await _render_rows(session, filter or None)
    # Track dashboard view (non-auto-refresh)
    try:
        from sqlalchemy import text as sql_text
        import uuid as _uuid
        u = request.state.user if hasattr(request, 'state') and hasattr(request.state, 'user') else None
        if u:
            await session.execute(sql_text(
                "INSERT INTO user_activity_events (company_id, user_id, session_id, event_type, route, occurred_at) "
                "VALUES ((SELECT id FROM subscribers LIMIT 1), :uid, :sid, 'dashboard_opened', '/dashboard/partial', NOW())"
            ), {"uid": u.get("username", "unknown"), "sid": str(_uuid.uuid4())})
            await session.commit()
    except Exception:
        pass
    return HTMLResponse(rows_html)


@router.post("/dashboard/{item_id}/resolve")
async def resolve_item(
    request: Request,
    item_id: UUID,
    correct_status: str = Form("G"),
    comment: str = Form(""),
    session: AsyncSession = Depends(get_db),
):
    """Resolve: set andon_status to Green, log event, return updated row list.
    If correct_status is provided (R/Y/G), log a classification correction."""
    repo = ScheduleRepository(session)

    if correct_status != "G" and correct_status in ("R", "Y", "G"):
        # This is a classification correction — log original vs new
        item = await repo.get(item_id)
        orig_status = item.andon_status if item else "?"
        await repo.update(item_id, andon_status=correct_status)
        detail = f"Classification corrected: {orig_status} → {correct_status}"
        if comment:
            detail += f" | {comment}"
        await _log_action(session, item_id, detail, "Feedback correction")
    else:
        # Normal resolve to Green
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
    cascade: str = Query("none"),
    selected_trades: str = Query(""),
    session: AsyncSession = Depends(get_db),
):
    """Push schedule dates by N days, with optional cascade to following trades.

    cascade:
      - "none"     — only this trade (default)
      - "next"     — this trade + the next scheduled trade on the same house
      - "selected" — this trade + trades listed in selected_trades
    """
    repo = ScheduleRepository(session)
    item = await repo.get(item_id)
    if not item:
        return HTMLResponse("", status_code=404)

    # Push the current trade
    updates = _build_push_updates(item, days)
    if updates:
        await repo.update(item_id, **updates)
    await _log_action(session, item_id, f"Push +{days} day(s)")

    # Cascade helpers
    async def _push_trade(trade_name: str) -> None:
        sibling = await repo.get_by_trade_and_house(item.house_id, trade_name)
        if sibling and sibling.id != item_id:
            su = _build_push_updates(sibling, days)
            if su:
                await repo.update(sibling.id, **su)
            await _log_action(session, sibling.id, f"Cascade push +{days} day(s) from {item.trade}")

    if cascade == "next":
        following_trades = _get_following_trades(item.trade)
        if following_trades:
            await _push_trade(following_trades[0])

    elif cascade == "selected" and selected_trades:
        targets = [t.strip() for t in selected_trades.split(",") if t.strip()]
        for t in targets:
            await _push_trade(t)

    await session.commit()
    # Track card action
    try:
        import uuid as _uuid
        from sqlalchemy import text as sql_text
        u = request.state.user if hasattr(request, 'state') and hasattr(request.state, 'user') else None
        if u:
            await session.execute(sql_text(
                "INSERT INTO user_activity_events (company_id, user_id, session_id, event_type, route, occurred_at) "
                "VALUES ((SELECT id FROM subscribers LIMIT 1), :uid, :sid, 'card_action_taken', '/dashboard/resolve', NOW())"
            ), {"uid": u.get("username", "unknown"), "sid": str(_uuid.uuid4())})
            await session.commit()
    except Exception:
        pass
    html = await _render_rows(session)
    return HTMLResponse(html)


@router.post("/dashboard/{item_id}/push-custom")
async def push_custom_item(
    request: Request,
    item_id: UUID,
    new_start_date: str = Form(...),
    cascade: str = Form("none"),
    selected_trades: str = Form(""),
    trade_dates: str = Form(""),
    notify: str = Form(""),
    session: AsyncSession = Depends(get_db),
):
    """Push schedule to a specific date, log event, return updated row list.

    cascade: "none" | "next" | "selected"
    When cascade="selected", trade_dates contains "trade:YYYY-MM-DD,..." pairs.
    notify contains comma-separated roles: "Boss,Office,Staff"
    """
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

        # Cascade to following trades
        if days_diff != 0:
            async def _push_cascade_trade(trade_name: str) -> None:
                sibling = await repo.get_by_trade_and_house(item.house_id, trade_name)
                if sibling and sibling.id != item_id:
                    su = _build_push_updates(sibling, days_diff)
                    if su:
                        await repo.update(sibling.id, **su)
                    await _log_action(session, sibling.id, f"Cascade push +{days_diff} day(s) from {item.trade} (custom date)")

            async def _set_trade_date(trade_name: str, target_date_str: str) -> None:
                """Set a specific date for a cascaded trade (per-trade calendar)."""
                try:
                    target_date = date.fromisoformat(target_date_str)
                except ValueError:
                    return
                sibling = await repo.get_by_trade_and_house(item.house_id, trade_name)
                if sibling and sibling.id != item_id:
                    td_updates = {"scheduled_start": target_date}
                    if sibling.scheduled_end:
                        # Shift end date by same offset as start date
                        sib_diff = (target_date - sibling.scheduled_start).days
                        td_updates["scheduled_end"] = sibling.scheduled_end + timedelta(days=sib_diff)
                    await repo.update(sibling.id, **td_updates)
                    await _log_action(session, sibling.id, f"Custom date set: {target_date}", f"From {item.trade}")

            if cascade == "next":
                following_trades = _get_following_trades(item.trade)
                if following_trades:
                    await _push_cascade_trade(following_trades[0])
            elif cascade == "selected" and trade_dates:
                # Parse "trade:YYYY-MM-DD,trade:YYYY-MM-DD" pairs
                for pair in trade_dates.split(","):
                    pair = pair.strip()
                    if ":" in pair:
                        t_name, t_date = pair.split(":", 1)
                        await _set_trade_date(t_name.strip(), t_date.strip())

        # ── Record schedule change group ──
        try:
            from sqlalchemy import text as sql_text
            change_scope = cascade if cascade != "none" else "this_trade_only"
            house_id_str = str(item.house_id) if item.house_id else None
            u = request.state.user if hasattr(request, 'state') and hasattr(request.state, 'user') else None
            username = u.get("username", "unknown") if u else "unknown"
            gid = await session.execute(sql_text(
                "INSERT INTO schedule_change_groups (project_id, change_scope, created_by) "
                "VALUES (:pid, :scope, :by) RETURNING id"
            ), {"pid": house_id_str, "scope": change_scope, "by": username})
            group_id = gid.fetchone()[0]
            await session.execute(sql_text(
                "INSERT INTO schedule_change_items (group_id, trade, house_id, original_date, proposed_date, date_type) "
                "VALUES (:gid, :trade, :hid, :orig, :prop, 'target')"
            ), {"gid": group_id, "trade": item.trade, "hid": house_id_str,
                "orig": item.scheduled_start, "prop": parsed})
            logger.info("Schedule change group %s recorded for %s", group_id, item.trade)
        except Exception as exc:
            logger.warning("Failed to record schedule change group: %s", exc)

        # ── Send notifications to selected roles ──
        if notify:
            from app.services.outbound import OutboundService
            from app.repositories.contact_repo import ContactRepository
            outbound = OutboundService()
            contact_repo = ContactRepository(session)
            contact = None
            if item.trade:
                contacts = await contact_repo.get_by_trade(item.trade)
                for c in contacts:
                    if c.is_active:
                        contact = c
                        break
                if not contact and contacts:
                    contact = contacts[0]
            roles = [r.strip() for r in notify.split(",") if r.strip()]
            address = item.house.address if item.house else "Unknown"
            msg = f"TLG Andon — Schedule updated: {item.trade} at {address}. New date: {new_start_date}."
            for role in roles:
                phone = None
                email = None
                if role == "Boss" and contact:
                    phone = contact.manager_phone
                    email = contact.email
                elif role == "Office" and contact:
                    phone = contact.phone
                    email = contact.email
                elif role == "Staff" and contact:
                    phone = contact.phone
                    email = contact.email
                if phone:
                    await outbound.send_sms(phone, msg, item.house_id, item.trade)
                if email:
                    logger.info("[EMAIL NOTIFY] To: %s Subject: TLG Andon Schedule Update Body: %s", email, msg)
                logger.info("Schedule notify: role=%s phone=%s email=%s msg=%s", role, phone, email, msg)

        await session.commit()

    html = await _render_rows(session)
    return HTMLResponse(html)


# ── Team members available for delegation ──
TEAM_MEMBERS = [
    {"name": "Brian (Owner)", "role": "owner"},
    {"name": "Clint (Foreman)", "role": "foreman"},
    {"name": "Office Admin", "role": "admin"},
    {"name": "Interior Designer", "role": "designer"},
]


@router.post("/dashboard/{item_id}/delegate")
async def delegate_item(
    request: Request,
    item_id: UUID,
    delegated_to: str = Form(""),
    delegation_note: str = Form(""),
    trade_name: str = Form(""),
    session: AsyncSession = Depends(get_db),
):
    """Delegate an issue — notify Boss/Office/Staff via SMS + email."""
    repo = ScheduleRepository(session)
    item = await repo.get(item_id)
    if not item:
        return HTMLResponse("", status_code=404)

    await repo.update(
        item_id,
        delegated_to=delegated_to,
        delegated_by="Jim (PM)",
        delegation_note=delegation_note,
        delegation_status="delegated",
    )

    detail = f"Delegated to: {delegated_to}"
    if delegation_note:
        detail += f" | Note: {delegation_note}"
    await _log_action(session, item_id, detail, "Delegation")

    # ── Send notifications ──
    from app.services.outbound import OutboundService
    outbound = OutboundService()

    # Get contact info for this trade
    from app.repositories.contact_repo import ContactRepository
    contact_repo = ContactRepository(session)
    contact = None
    if item.trade:
        contacts = await contact_repo.get_by_trade(item.trade)
        # Use the first active contact
        for c in contacts:
            if c.is_active:
                contact = c
                break
        if not contact and contacts:
            contact = contacts[0]

    roles = [r.strip() for r in delegated_to.split(",") if r.strip()]
    house = item.house
    address = house.address if house else "Unknown"
    msg_body = f"TLG Andon — Delegation: {trade_name or item.trade} issue at {address}. {delegation_note}" if delegation_note else f"TLG Andon — Delegation: {trade_name or item.trade} issue at {address}."

    for role in roles:
        phone = None
        email = None
        if role == "Boss" and contact:
            phone = contact.manager_phone
            email = contact.email  # Boss gets the same email for now
        elif role == "Office" and contact:
            phone = contact.phone
            email = contact.email
        elif role == "Staff" and contact:
            phone = contact.phone  # Staff uses main contact as fallback
            email = contact.email

        if phone:
            await outbound.send_sms(phone, msg_body, item.house_id, item.trade)
        # Send email notification when email is available
        if email:
            logger.info("[EMAIL NOTIFY] To: %s Subject: TLG Andon Delegation Body: %s", email, msg_body)
        logger.info("Delegate notify: role=%s phone=%s email=%s msg=%s", role, phone, email, msg_body)

    await session.commit()

    html = await _render_rows(session)
    return HTMLResponse(html)


@router.post("/dashboard/{item_id}/delegation-update")
async def update_delegation_status(
    request: Request,
    item_id: UUID,
    new_status: str = Form(""),
    session: AsyncSession = Depends(get_db),
):
    """Update the delegation status (In Progress, Resolved, Reclaimed)."""
    repo = ScheduleRepository(session)
    item = await repo.get(item_id)
    if not item:
        return HTMLResponse("", status_code=404)

    if new_status == "reclaimed":
        await repo.update(
            item_id,
            delegated_to="",
            delegated_by="",
            delegation_note="",
            delegation_status="",
        )
        await _log_action(session, item_id, "Delegation reclaimed by PM", "Delegation")
    elif new_status == "resolved":
        await repo.update(item_id, delegation_status="resolved")
        await _log_action(session, item_id, "Delegation marked resolved", "Delegation")
    elif new_status == "in_progress":
        await repo.update(item_id, delegation_status="in_progress")
        await _log_action(session, item_id, "Delegation marked in progress", "Delegation")

    await session.commit()

    html = await _render_rows(session)
    return HTMLResponse(html)


@router.post("/dashboard/classify/{event_id}/correct")
async def correct_classification(
    request: Request,
    event_id: UUID,
    correct_status: str = Query(...),
    comment: str = Query(""),
    session: AsyncSession = Depends(get_db),
):
    """
    Correction feedback endpoint.

    Jim can mark a previous classification as wrong and set the correct status.
    Logs the correction as an Event and updates the schedule item status.
    Used to build a correction log for future classifier tuning.

    Query params:
      correct_status: 'R', 'Y', or 'G' — what the status SHOULD have been
      comment: Optional short note explaining why it was corrected
    """
    if correct_status not in ("R", "Y", "G"):
        return HTMLResponse("Invalid status", status_code=400)

    # Find the original event
    event_repo = BaseRepository(session, Event)
    original = await event_repo.get(event_id)
    if not original:
        return HTMLResponse("Event not found", status_code=404)

    # Build the correction text with optional comment
    correction_text = (
        f"[CLASSIFICATION CORRECTION] Event {event_id}: "
        f"original={original.outcome or 'none'} "
        f"corrected={correct_status}"
    )
    if comment:
        correction_text += f" | comment: {comment}"

    # Log the correction as a new Event
    await event_repo.create(
        direction="outbound",
        channel="sms",
        full_text=correction_text,
        house_id=original.house_id,
        schedule_item_id=original.schedule_item_id,
        trade=original.trade,
        outcome=correct_status,
        triggered_by="pm",
    )

    # If there's a schedule item, update its status
    if original.schedule_item_id:
        schedule_repo = ScheduleRepository(session)
        await schedule_repo.update(original.schedule_item_id, andon_status=correct_status)

    await session.commit()
    logger.info("Classification corrected: event=%s original=%s -> %s (comment: %s)",
                event_id, original.outcome, correct_status, comment or "-")

    # Return updated dashboard rows
    html = await _render_rows(session)
    return HTMLResponse(html)
