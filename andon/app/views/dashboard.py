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

# ── Contextual quick actions per trade ──
# Each action: {label, icon, action, href_template or message_template}
CONTEXTUAL_ACTIONS = {
    "foundation_concrete": [
        {"label": "Check Cure Time", "icon": "⏱", "action": "prefill_note", "message": "Check cure time status for {address} — has the concrete reached minimum PSI?"},
        {"label": "Call Concrete Co.", "icon": "📞", "action": "call_contact"},
        {"label": "Flag Re-pour", "icon": "🔄", "action": "prefill_note", "message": "Possible re-pour needed at {address} — verify with engineer before proceeding."},
    ],
    "framing": [
        {"label": "Check Truss Specs", "icon": "📐", "action": "prefill_note", "message": "Verify truss specifications at {address} — check for damage on delivery."},
        {"label": "Call Supplier", "icon": "📞", "action": "call_contact"},
        {"label": "Request Inspection", "icon": "🔍", "action": "prefill_note", "message": "Schedule framing inspection at {address} — ready for review."},
    ],
    "plumbing_rough": [
        {"label": "Check Venting", "icon": "🔧", "action": "prefill_note", "message": "Verify venting is correct at {address} before drywall goes up."},
        {"label": "Schedule Inspection", "icon": "🔍", "action": "prefill_note", "message": "Plumbing rough-in ready for inspection at {address}."},
    ],
    "hvac_rough": [
        {"label": "Check Ductwork", "icon": "🌀", "action": "prefill_note", "message": "Verify ductwork layout at {address} before drywall enclosure."},
        {"label": "Schedule Inspection", "icon": "🔍", "action": "prefill_note", "message": "HVAC rough-in ready for inspection at {address}."},
    ],
    "electrical_rough": [
        {"label": "Check Boxes", "icon": "💡", "action": "prefill_note", "message": "Verify all electrical boxes are correctly placed at {address}."},
        {"label": "Schedule Inspection", "icon": "🔍", "action": "prefill_note", "message": "Electrical rough-in ready for inspection at {address}."},
    ],
    "drywall_plaster": [
        {"label": "Check Moisture", "icon": "💧", "action": "prefill_note", "message": "Check moisture levels at {address} before drywall installation."},
        {"label": "Flag Delays", "icon": "⏳", "action": "prefill_note", "message": "Drywall crew delayed at {address} — update schedule."},
    ],
    "paint": [
        {"label": "Check Prep Work", "icon": "🎨", "action": "prefill_note", "message": "Verify surface prep complete at {address} before painting starts."},
        {"label": "Touch-up List", "icon": "📋", "action": "prefill_note", "message": "Compile touch-up items at {address} for final walkthrough."},
    ],
    "flooring": [
        {"label": "Check Subfloor", "icon": "🏗", "action": "prefill_note", "message": "Verify subfloor condition at {address} before flooring installation."},
        {"label": "Verify Material", "icon": "📦", "action": "prefill_note", "message": "Confirm flooring material has arrived at {address} and is correct."},
    ],
    "cabinets": [
        {"label": "Check Dimensions", "icon": "📏", "action": "prefill_note", "message": "Verify cabinet dimensions at {address} match the plans."},
        {"label": "Verify Hardware", "icon": "🔩", "action": "prefill_note", "message": "Confirm all cabinet hardware has arrived at {address}."},
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
# ESCALATION CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Default escalation groups
DEFAULT_ESCALATION_GROUPS = {
    "Critical Issues Group": {
        "members": ["Brian (Owner)", "Clint (Foreman)"],
        "trigger_red_hours": 4,          # Alert if Red open > 4 hours
        "trigger_multi_red": 2,           # Alert if 2+ Red on same house
        "trigger_keywords": ["structural", "safety", "fire", "flood", "gas leak", "collapse", "electrical fire"],
    },
    "Owner Only": {
        "members": ["Brian (Owner)"],
        "trigger_red_hours": 8,           # Alert if Red open > 8 hours
        "trigger_multi_red": 3,           # Alert if 3+ Red on same house
        "trigger_keywords": [],
    },
}

import json
from pathlib import Path

ESCALATION_CONFIG_FILE = Path(__file__).parent.parent / "escalation_config.json"


def _load_escalation_config() -> dict:
    """Load escalation group configuration from JSON file."""
    if ESCALATION_CONFIG_FILE.exists():
        try:
            with open(ESCALATION_CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_ESCALATION_GROUPS)


def _check_escalations(items: list[dict]) -> list[dict]:
    """Evaluate items against escalation triggers. Returns list of escalation messages."""
    from datetime import datetime, timezone, timedelta

    cfg = _load_escalation_config()
    escalations = []
    now = datetime.now(timezone.utc)

    # Group items by house
    by_house: dict[str, list[dict]] = {}
    for item in items:
        by_house.setdefault(item["house_id"], []).append(item)

    for group_name, group in cfg.items():
        trigger_hours = group.get("trigger_red_hours", 99)
        trigger_multi = group.get("trigger_multi_red", 99)
        trigger_kw = [k.lower() for k in group.get("trigger_keywords", [])]
        members = group.get("members", [])

        # Check each Red item for time-based escalation
        for item in items:
            if item["andon_status"] != "R":
                continue
            last_touch = item.get("last_touch_ts")
            if not last_touch:
                continue
            # Calculate how long Red has been open
            if isinstance(last_touch, datetime):
                hours_open = (now - last_touch).total_seconds() / 3600
                if hours_open >= trigger_hours:
                    escalations.append({
                        "group": group_name,
                        "members": ", ".join(members),
                        "reason": f"Red issue open for {int(hours_open)} hours",
                        "message": f"🚨 ESCALATION: {item['address']} — {item['trade_display']} issue has been open for {int(hours_open)} hours with no resolution. Current status: {item['activity_label']}",
                        "address": item["address"],
                        "trade": item["trade_display"],
                        "item_id": item["id"],
                    })

        # Check for multiple Red issues on same house
        for house_id, house_items in by_house.items():
            red_items = [i for i in house_items if i["andon_status"] == "R"]
            if len(red_items) >= trigger_multi:
                addr = red_items[0]["address"]
                trades = ", ".join(i["trade_display"] for i in red_items)
                escalations.append({
                    "group": group_name,
                    "members": ", ".join(members),
                    "reason": f"{len(red_items)} Red issues on same house",
                    "message": f"🚨 ESCALATION: {addr} has {len(red_items)} active Red issues ({trades}). Requires immediate attention.",
                    "address": addr,
                    "trade": trades,
                    "item_id": red_items[0]["id"],
                })

        # Check for keyword-based escalations
        for item in items:
            msg = (item.get("last_message") or "").lower()
            for kw in trigger_kw:
                if kw in msg:
                    if not any(e["address"] == item["address"] and e["reason"] == f"Keyword: {kw}" for e in escalations):
                        escalations.append({
                            "group": group_name,
                            "members": ", ".join(members),
                            "reason": f"Keyword: {kw}",
                            "message": f"🚨 ESCALATION: {item['address']} — {item['trade_display']} issue contains high-severity keyword '{kw}': {item['last_message'][:100]}",
                            "address": item["address"],
                            "trade": item["trade_display"],
                            "item_id": item["id"],
                        })

    # Deduplicate by message content
    seen = set()
    unique = []
    for e in escalations:
        if e["message"] not in seen:
            seen.add(e["message"])
            unique.append(e)

    return unique[:5]  # Max 5 escalation banners at once

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


async def _get_red_yellow_items(session: AsyncSession) -> list[dict]:
    """Query all schedule items with R or Y status, joined with houses and latest event."""
    stmt = (
        select(ScheduleItem)
        .options(selectinload(ScheduleItem.house))
        .where(ScheduleItem.andon_status.in_(["R", "Y"]))
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
    escalations = _check_escalations(items)

    html = _render(
        "dashboard.html",
        items=items,
        today=today,
        red_count=red_count,
        yellow_count=yellow_count,
        escalations=escalations,
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
    correct_status: str = "G",
    comment: str = "",
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
    session: AsyncSession = Depends(get_db),
):
    """Delegate an issue to one or more internal team members."""
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
