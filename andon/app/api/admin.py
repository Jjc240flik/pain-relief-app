"""
Admin endpoints for managing the ClassifierEngine and system monitoring.

Provides:
  POST /admin/import-keywords — Import graded keywords from the Excel checklist
  GET  /admin/analytics     — System monitoring and analytics dashboard
"""

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import async_session, get_db
from app.models.event import Event
from app.models.schedule_item import ScheduleItem
from app.repositories.base import BaseRepository
from app.services.auth import require_admin, require_owner
from app.services.keyword_loader import load_keywords_from_excel, format_report
from app.services.classifier import load_graded_rules
from app.views.dashboard import _render  # Reuse Jinja2 rendering

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# Expected location of the graded Excel file
EXCEL_PATH = Path(__file__).parent.parent.parent / "keywords_and_phrases_checklist.xlsx"


@router.post("/import-keywords")
async def import_keywords(user: dict = Depends(require_owner)) -> Response:
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


@router.get("/keywords", response_class=HTMLResponse)
async def keywords_page(request: Request, user: dict = Depends(require_owner)):
    """Render the keyword import page with upload form."""
    html = _render("admin/keywords.html", request=request, result=None)
    return HTMLResponse(html)


@router.post("/upload-keywords")
async def upload_keywords(request: Request, user: dict = Depends(require_owner)):
    """Accept uploaded Excel file, validate, import, and show results."""
    form = await request.form()
    file = form.get("file")
    if not file:
        html = _render("admin/keywords.html", request=request, result=None, error="Please select a file.")
        return HTMLResponse(html)

    # Save to temp location
    import tempfile
    import os
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        result = load_keywords_from_excel(tmp.name)
        load_graded_rules()
        report = format_report(result)

        html = _render("admin/keywords.html", request=request, result=result, report=report)
        return HTMLResponse(html)
    except Exception as exc:
        logger.error("Keyword import failed: %s", exc)
        html = _render("admin/keywords.html", request=request, result=None, error=str(exc))
        return HTMLResponse(html)
    finally:
        os.unlink(tmp.name)


@router.get("/escalations", response_class=HTMLResponse)
async def escalation_history(request: Request, user: dict = Depends(require_owner)):
    """Show escalation history from the database."""
    from sqlalchemy import text as sql_text

    async with async_session() as session:
        result = await session.execute(sql_text(
            "SELECT id, house_address, trade, reason, message, status, "
            "to_char(created_at, 'Mon DD, YYYY HH24:MI') as created "
            "FROM escalations ORDER BY created_at DESC LIMIT 50"
        ))
        rows = result.fetchall()

    html = _render("admin/escalations.html", request=request, escalations=rows)
    return HTMLResponse(html)


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
    days: int = Query(30, alias="days", ge=1, le=365),
    subscriber_id: str = Query("", alias="sub"),
    user: dict = Depends(require_owner),
):
    """Render the admin analytics dashboard with usage, cost, and health metrics.

    If subscriber_id is provided, filters by that subscriber.
    Otherwise shows all subscribers combined.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    today = date.today()

    async with async_session() as session:
        # Build subscriber filter
        sub_filter = []
        sub_name = "All Subscribers Combined"
        if subscriber_id:
            from sqlalchemy import text as sql_text
            sub_row = (await session.execute(
                sql_text("SELECT company_name FROM subscribers WHERE id = :id"),
                {"id": subscriber_id}
            )).fetchone()
            if sub_row:
                sub_name = sub_row[0]
                sub_filter = [Event.subscriber_id == subscriber_id]

        # Usage
        channel_counts = defaultdict(int)
        stmt = select(Event.channel, Event.direction, func.count().label("c")).where(
            Event.timestamp >= since, *sub_filter).group_by(Event.channel, Event.direction)
        for row in (await session.execute(stmt)):
            channel_counts[row.channel] += row.c

        mms_stmt = select(func.count()).select_from(Event).where(
            Event.channel == "sms", Event.raw_payload.isnot(None),
            Event.timestamp >= since, *sub_filter)
        mms_count = (await session.execute(mms_stmt)).scalar() or 0
        voice_stmt = select(func.count()).select_from(Event).where(
            Event.channel == "voice_message", Event.timestamp >= since, *sub_filter)
        voice_count = (await session.execute(voice_stmt)).scalar() or 0
        total_stmt = select(func.count()).select_from(Event).where(
            Event.timestamp >= since, *sub_filter)
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
                    Event.timestamp >= ds, Event.timestamp < de, *sub_filter).group_by(Event.channel))):
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
                Event.outcome == "R", Event.timestamp >= since, *sub_filter))).scalar() or 0
        yellow = (await session.execute(
            select(func.count()).select_from(Event).where(
                Event.outcome == "Y", Event.timestamp >= since, *sub_filter))).scalar() or 0
        corr = (await session.execute(
            select(func.count()).select_from(Event).where(
                Event.full_text.like("[CLASSIFICATION CORRECTION]%"),
                Event.timestamp >= since, *sub_filter))).scalar() or 0
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
                Event.timestamp >= since, *sub_filter
            ).group_by(Event.trade).order_by(desc("c")).limit(10)))
        trade_breakdown = [{"trade": r.trade, "count": r.c} for r in trade_rows]

        # Top subs
        sub_rows = (await session.execute(
            select(Event.sender_phone, func.count().label("c")).where(
                Event.outcome.isnot(None), Event.timestamp >= since,
                Event.sender_phone.isnot(None), *sub_filter
            ).group_by(Event.sender_phone).order_by(desc("c")).limit(10)))
        top_subs = [{"sender": r.sender_phone, "count": r.c} for r in sub_rows]

        # System health
        media_evt = (await session.execute(
            select(func.count()).select_from(Event).where(
                Event.raw_payload.isnot(None), Event.timestamp >= since, *sub_filter))).scalar() or 0
        sched_cnt = (await session.execute(
            select(func.count()).select_from(ScheduleItem))).scalar() or 0
        health = {
            "total_schedules": sched_cnt, "media_events": media_evt,
            "error_count": 0, "avg_resolution_hours": None,
        }

        # Get all subscribers for the filter dropdown
        from sqlalchemy import text as sql_text
        all_subs = (await session.execute(
            sql_text("SELECT id, company_name FROM subscribers ORDER BY company_name")
        )).fetchall()

    html = _render("admin/analytics.html",
        request=request, days=days, usage=usage, usage_trends=trends,
        costs=costs, issues=issues, trade_breakdown=trade_breakdown,
        top_subs=top_subs, health=health, today=today, rates=DEFAULT_RATES,
        alerts=_check_alerts(_load_alerts(), usage, costs, health),
        subscribers=all_subs, current_sub_id=subscriber_id, sub_name=sub_name,
    )
    return HTMLResponse(html)


# ── Trade display labels ──
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


@router.get("/scorecard", response_class=HTMLResponse)
async def subcontractor_scorecard(
    request: Request,
    trade: str = Query("", alias="trade"),
    sort: str = Query("red_desc", alias="sort"),
    user: dict = Depends(require_owner),
):
    """Render the subcontractor performance scorecard."""
    from app.models.contact import Contact

    async with async_session() as session:
        stmt = select(Contact).where(Contact.is_active == True)
        result = await session.execute(stmt)
        contacts = result.scalars().all()

        scorecard = []
        for c in contacts:
            if not c.phone and not c.email:
                continue
            identifier = c.phone or c.email
            contact_trade = c.trade or ""

            # Filter by trade
            if trade and contact_trade != trade:
                continue

            # Count Red events
            red_stmt = select(func.count()).select_from(Event).where(
                Event.outcome == "R",
                Event.sender_phone == c.phone if c.phone else False,
            )
            red = 0
            if c.phone:
                red = (await session.execute(
                    select(func.count()).select_from(Event).where(
                        Event.outcome == "R", Event.sender_phone == c.phone)
                )).scalar() or 0

            # Count Yellow events
            yellow = (await session.execute(
                select(func.count()).select_from(Event).where(
                    Event.outcome == "Y", Event.sender_phone == c.phone)
            )).scalar() or 0 if c.phone else 0

            # Count "Behind" flags — events where this sub was flagged as Behind
            behind = (await session.execute(
                select(func.count()).select_from(Event).where(
                    Event.full_text.like("%Behind%"),
                    Event.sender_phone == c.phone,
                )
            )).scalar() or 0 if c.phone else 0

            # Count corrections applied TO this sub's events
            corrections = (await session.execute(
                select(func.count()).select_from(Event).where(
                    Event.full_text.like("%Classification corrected%"),
                    Event.trade == trade,
                )
            )).scalar() or 0 if trade else 0

            # Average response time — time between outbound check-in and inbound reply
            avg_response_hours = None
            # Count delegation assignments for this sub's trade
            from app.models.schedule_item import ScheduleItem
            deleg_stmt = select(func.count()).select_from(ScheduleItem).where(
                ScheduleItem.delegation_status.in_(["delegated", "in_progress", "resolved"]),
                ScheduleItem.trade == trade,
            )
            deleg_count = (await session.execute(deleg_stmt)).scalar() or 0 if trade else 0

            # Delegation completion
            deleg_done = (await session.execute(
                select(func.count()).select_from(ScheduleItem).where(
                    ScheduleItem.delegation_status == "resolved",
                    ScheduleItem.trade == trade,
                )
            )).scalar() or 0 if trade else 0

            scorecard.append({
                "name": c.name or identifier,
                "company": c.company or "",
                "phone": c.phone or "",
                "trade": contact_trade,
                "trade_display": TRADE_LABELS.get(contact_trade, contact_trade.replace("_", " ").title()),
                "red": red,
                "yellow": yellow,
                "behind": behind,
                "corrections": corrections,
                "avg_response_hours": avg_response_hours,
                "delegations": deleg_count,
                "delegations_done": deleg_done,
                "delegation_rate": round(deleg_done / deleg_count * 100, 0) if deleg_count > 0 else 0,
                "total_issues": red + yellow,
            })

        # Sorting
        sort_key = sort.replace("_desc", "").replace("_asc", "")
        reverse = sort.endswith("_desc")
        scorecard.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=reverse)

    html = _render("admin/scorecard.html",
        request=request,
        subs=scorecard,
        sort=sort,
        trade_filter=trade,
        trades=TRADE_LABELS,
    )
    return HTMLResponse(html)


# ── CSV import helper ──
def _parse_csv_contacts(content: str) -> list[dict]:
    import csv, io
    reader = csv.DictReader(io.StringIO(content))
    contacts = []
    for row in reader:
        name = (row.get("name") or row.get("Name") or "").strip()
        if not name:
            continue
        contacts.append({
            "name": name,
            "company": (row.get("company") or row.get("Company") or "").strip(),
            "trade": (row.get("trade") or row.get("Trade") or "").strip().lower().replace(" ", "_"),
            "phone": (row.get("phone") or row.get("Phone") or "").strip(),
            "email": (row.get("email") or row.get("Email") or "").strip().lower(),
            "manager_phone": (row.get("manager_phone") or row.get("Manager Phone") or "").strip(),
            "notes": (row.get("notes") or row.get("Notes") or "").strip(),
        })
    return contacts


@router.get("/contacts", response_class=HTMLResponse)
async def list_contacts(
    request: Request,
    search: str = Query("", alias="q"),
    trade: str = Query("", alias="trade"),
):
    from app.models.contact import Contact
    async with async_session() as session:
        stmt = select(Contact).where(Contact.is_active == True).order_by(Contact.name)
        if trade:
            stmt = stmt.where(Contact.trade == trade)
        result = await session.execute(stmt)
        candidates = result.scalars().all()
        search_lower = search.strip().lower()
        if search_lower:
            candidates = [c for c in candidates if (
                search_lower in (c.name or "").lower()
                or search_lower in (c.company or "").lower()
                or search_lower in (c.phone or "")
                or search_lower in (c.email or "").lower())]

    html = _render("admin/contacts.html",
        request=request, contacts=candidates,
        search=search, trade_filter=trade, trades=TRADE_LABELS,
    )
    return HTMLResponse(html)


@router.post("/contacts/add")
async def add_contact(
    request: Request,
    name: str = Form(""), company: str = Form(""),
    trade: str = Form(""), phone: str = Form(""),
    email: str = Form(""), manager_phone: str = Form(""),
    notes: str = Form(""),
):
    from app.models.contact import Contact
    if not name.strip():
        return HTMLResponse("Name required", status_code=400)
    async with async_session() as session:
        repo = BaseRepository(session, Contact)
        await repo.create(name=name.strip(), company=company.strip(),
            trade=trade.strip(), phone=phone.strip(),
            email=email.strip().lower(), manager_phone=manager_phone.strip(),
            notes=notes.strip(), is_active=True)
        await session.commit()
    return HTMLResponse("", status_code=303, headers={"Location": "/admin/contacts"})


@router.post("/contacts/{contact_id}/edit")
async def edit_contact(
    request: Request, contact_id: UUID,
    name: str = Form(""), company: str = Form(""),
    trade: str = Form(""), phone: str = Form(""),
    email: str = Form(""), manager_phone: str = Form(""),
    notes: str = Form(""),
):
    from app.models.contact import Contact
    async with async_session() as session:
        repo = BaseRepository(session, Contact)
        if not await repo.get(contact_id):
            return HTMLResponse("Not found", status_code=404)
        await repo.update(contact_id,
            name=name.strip(), company=company.strip(), trade=trade.strip(),
            phone=phone.strip(), email=email.strip().lower(),
            manager_phone=manager_phone.strip(), notes=notes.strip())
        await session.commit()
    return HTMLResponse("", status_code=303, headers={"Location": "/admin/contacts"})


@router.post("/contacts/{contact_id}/delete")
async def delete_contact(request: Request, contact_id: UUID):
    from app.models.contact import Contact
    async with async_session() as session:
        repo = BaseRepository(session, Contact)
        await repo.update(contact_id, is_active=False)
        await session.commit()
    return HTMLResponse("", status_code=303, headers={"Location": "/admin/contacts"})


@router.post("/contacts/import")
async def import_contacts(request: Request):
    from app.models.contact import Contact
    form = await request.form()
    file = form.get("file")
    if not file:
        return HTMLResponse("No file", status_code=400)
    text = (await file.read()).decode("utf-8-sig")
    contacts = _parse_csv_contacts(text)
    if not contacts:
        return HTMLResponse("No valid contacts", status_code=400)

    imported = updated = skipped = 0
    async with async_session() as session:
        repo = BaseRepository(session, Contact)
        for c in contacts:
            if not c["phone"] and not c["email"]:
                skipped += 1; continue
            existing = None
            if c["phone"]:
                existing = (await session.execute(
                    select(Contact).where(Contact.phone == c["phone"]))).scalar_one_or_none()
            if existing:
                await repo.update(existing.id, **c)
                updated += 1
            else:
                await repo.create(**c, is_active=True)
                imported += 1
        await session.commit()

    # Re-render with result message
    html = _render("admin/contacts.html",
        request=request, contacts=[], search="", trade_filter="", trades=TRADE_LABELS,
        import_result=f"Imported: {imported}, Updated: {updated}, Skipped: {skipped}",
    )
    return HTMLResponse(html)


# ═══════════════════════════════════════════════════════════════
# USAGE ALERTS
# ═══════════════════════════════════════════════════════════════

ALERTS_CONFIG_FILE = Path(__file__).parent.parent.parent / "alerts_config.json"

DEFAULT_ALERTS = {
    "monthly_spend_limit": 50.0,
    "monthly_spend_enabled": True,
    "daily_msg_limit": 200,
    "daily_msg_enabled": True,
    "media_storage_limit_mb": 500,
    "media_storage_enabled": True,
    "alert_email": "",
}


def _load_alerts() -> dict:
    if ALERTS_CONFIG_FILE.exists():
        try:
            with open(ALERTS_CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_ALERTS)


def _save_alerts(cfg: dict) -> None:
    with open(ALERTS_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def _check_alerts(cfg: dict, usage: dict, costs: dict, health: dict) -> list[dict]:
    alerts = []
    if cfg.get("monthly_spend_enabled") and costs.get("monthly_projected", 0) > cfg.get("monthly_spend_limit", 9999):
        alerts.append({"level": "warning", "icon": "💰", "title": "Monthly spend limit exceeded",
                       "message": f"Projected ${costs['monthly_projected']:.2f} exceeds limit of ${cfg['monthly_spend_limit']:.2f}"})
    if cfg.get("daily_msg_enabled"):
        daily_total = usage.get("sms", 0) + usage.get("mms", 0) + usage.get("voice", 0)
        if daily_total > cfg.get("daily_msg_limit", 9999):
            alerts.append({"level": "warning", "icon": "📨", "title": "Daily message volume high",
                           "message": f"{daily_total} messages exceeds limit of {cfg['daily_msg_limit']}"})
    if cfg.get("media_storage_enabled") and health.get("media_events", 0) > cfg.get("media_storage_limit_mb", 9999):
        alerts.append({"level": "info", "icon": "📸", "title": "Media storage growing",
                       "message": f"{health['media_events']} media events exceeds limit of {cfg['media_storage_limit_mb']}"})
    return alerts


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request, user: dict = Depends(require_owner)):
    cfg = _load_alerts()
    html = _render("admin/alerts.html", request=request, cfg=cfg, saved=request.query_params.get("saved", ""))
    return HTMLResponse(html)


@router.post("/alerts/save")
async def save_alerts(
    request: Request,
    monthly_spend_limit: float = Form(50.0),
    monthly_spend_enabled: str = Form(""),
    daily_msg_limit: int = Form(200),
    daily_msg_enabled: str = Form(""),
    media_storage_limit_mb: int = Form(500),
    media_storage_enabled: str = Form(""),
    alert_email: str = Form(""),
):
    cfg = {
        "monthly_spend_limit": monthly_spend_limit,
        "monthly_spend_enabled": monthly_spend_enabled == "on",
        "daily_msg_limit": daily_msg_limit,
        "daily_msg_enabled": daily_msg_enabled == "on",
        "media_storage_limit_mb": media_storage_limit_mb,
        "media_storage_enabled": media_storage_enabled == "on",
        "alert_email": alert_email.strip(),
    }
    _save_alerts(cfg)
    return HTMLResponse("", status_code=303, headers={"Location": "/admin/alerts?saved=1"})


# ── Subscriber Management ──

@router.get("/subscribers", response_class=HTMLResponse)
async def admin_subscribers(
    request: Request,
    user: dict = Depends(require_owner),
):
    """List all subscriber companies."""
    from sqlalchemy import text as sql_text
    async with async_session() as session:
        result = await session.execute(sql_text(
            "SELECT id, company_name, contact_name, contact_email, contact_phone, "
            "state, city, is_paid, subscription_plan, subscribed_at, is_active "
            "FROM subscribers ORDER BY company_name"
        ))
        rows = result.fetchall()
    html = _render("admin/subscribers.html", request=request, subscribers=rows, user=user)
    return HTMLResponse(html)


@router.get("/subscribers/summary", response_class=HTMLResponse)
async def admin_subscribers_summary(
    request: Request,
    user: dict = Depends(require_owner),
):
    """Aggregated totals of all subscribers."""
    from sqlalchemy import text as sql_text
    async with async_session() as session:
        total = (await session.execute(sql_text("SELECT count(*) FROM subscribers"))).scalar() or 0
        paid = (await session.execute(sql_text("SELECT count(*) FROM subscribers WHERE is_paid = true"))).scalar() or 0
        active = (await session.execute(sql_text("SELECT count(*) FROM subscribers WHERE is_active = true"))).scalar() or 0
        by_state = (await session.execute(sql_text(
            "SELECT state, count(*) FROM subscribers WHERE state != '' GROUP BY state ORDER BY count(*) DESC"
        ))).fetchall()
    html = _render("admin/subscribers_summary.html",
        request=request, total=total, paid=paid, active=active, by_state=by_state, user=user)
    return HTMLResponse(html)


# ── Project Onboarding ──

@router.get("/projects", response_class=HTMLResponse)
async def admin_projects_list(
    request: Request,
    user: dict = Depends(require_admin),
):
    """List all projects."""
    from sqlalchemy import text as sql_text
    async with async_session() as session:
        rows = (await session.execute(sql_text(
            "SELECT id, project_name, street_address, city, state, project_status, "
            "estimated_start, target_start, schedule_maturity, created_at "
            "FROM projects ORDER BY created_at DESC"
        ))).fetchall()
    html = _render("admin/projects_list.html", request=request, projects=rows, user=user)
    return HTMLResponse(html)


@router.get("/projects/new", response_class=HTMLResponse)
async def admin_project_new(
    request: Request,
    user: dict = Depends(require_admin),
):
    """Render the multi-section project onboarding form."""
    from sqlalchemy import text as sql_text
    async with async_session() as session:
        contacts = (await session.execute(sql_text(
            "SELECT id, name, company, trade, phone, email FROM contacts ORDER BY name"
        ))).fetchall()
    html = _render("admin/project_new.html",
        request=request, user=user,
        contacts=contacts, trade_labels=TRADE_LABELS,
    )
    return HTMLResponse(html)


@router.post("/projects/new", response_class=HTMLResponse)
async def admin_project_create(request: Request, user: dict = Depends(require_admin)):
    """Save a new project from the onboarding form."""
    from sqlalchemy import text as sql_text
    from datetime import date
    form = await request.form()

    project_name = (form.get("project_name") or "").strip()
    street_address = (form.get("street_address") or "").strip()
    if not project_name or not street_address:
        return HTMLResponse("Project name and address required", status_code=400)

    city = (form.get("city") or "").strip()
    state = (form.get("state") or "").strip()
    zip_code = (form.get("zip_code") or "").strip()
    community = (form.get("community") or "").strip()
    internal_number = (form.get("internal_number") or "").strip()
    owner_name = (form.get("owner_name") or "").strip()
    superintendent = (form.get("superintendent") or "").strip()
    project_manager = (form.get("project_manager") or "").strip()
    notes = (form.get("notes") or "").strip()
    project_status = (form.get("project_status") or "planning").strip()
    current_phase = (form.get("current_phase") or "").strip()
    current_trade = (form.get("current_trade") or "").strip()
    next_planned = (form.get("next_planned_trade") or "").strip()

    estimated_start = form.get("estimated_start") or None
    target_start = form.get("target_start") or None
    estimated_completion = form.get("estimated_completion") or None
    target_completion = form.get("target_completion") or None

    # Determine schedule maturity
    has_target = bool(target_start or target_completion)
    has_estimated = bool(estimated_start or estimated_completion)
    if has_target:
        maturity = "target_schedule"
    elif has_estimated:
        maturity = "estimated_only"
    else:
        maturity = "no_schedule"

    async with async_session() as session:
        subscriber_id = (await session.execute(
            sql_text("SELECT id FROM subscribers LIMIT 1")
        )).scalar()
        proj = (await session.execute(sql_text(
            """INSERT INTO projects (subscriber_id, project_name, street_address, city, state, zip_code,
               community, internal_number, owner_name, assigned_superintendent, assigned_project_manager,
               notes, project_status, current_phase, current_trade, next_planned_trade,
               estimated_start, target_start, estimated_completion, target_completion,
               schedule_maturity)
               VALUES (:sub, :name, :addr, :city, :st, :zip, :comm, :intn, :own, :supe, :pm,
               :notes, :pstat, :phase, :trade, :next, :estart, :tstart, :ecomp, :tcomp, :mat)
               RETURNING id"""),
            {"sub": subscriber_id, "name": project_name, "addr": street_address,
             "city": city, "st": state, "zip": zip_code, "comm": community,
             "intn": internal_number, "own": owner_name, "supe": superintendent,
             "pm": project_manager, "notes": notes, "pstat": project_status,
             "phase": current_phase, "trade": current_trade, "next": next_planned,
             "estart": estimated_start, "tstart": target_start,
             "ecomp": estimated_completion, "tcomp": target_completion,
             "mat": maturity}
        ))
        project_id = proj.fetchone()[0]

        # Link selected contacts
        selected_contact_ids = form.getlist("contact_id")
        selected_roles = form.getlist("contact_role")
        for i, cid in enumerate(selected_contact_ids):
            if cid.strip():
                role = selected_roles[i].strip() if i < len(selected_roles) else ""
                await session.execute(sql_text(
                    "INSERT INTO project_contacts (project_id, contact_id, role) VALUES (:pid, :cid, :role)"
                ), {"pid": project_id, "cid": cid.strip(), "role": role})

        # Save trade schedule rows
        trade_names = form.getlist("trade_name")
        trade_contacts = form.getlist("trade_contact_id")
        trade_estarts = form.getlist("trade_estimated_start")
        trade_tstarts = form.getlist("trade_target_start")
        trade_durations = form.getlist("trade_duration")
        trade_tcomps = form.getlist("trade_target_completion")
        trade_preceding = form.getlist("trade_preceding")
        trade_inspections = form.getlist("trade_inspection")
        trade_critical = form.getlist("trade_critical")
        trade_notes = form.getlist("trade_notes")

        for i, tn in enumerate(trade_names):
            tn = tn.strip()
            if not tn:
                continue
            insp = (trade_inspections[i].strip() if i < len(trade_inspections) else "") == "on"
            crit = (trade_critical[i].strip() if i < len(trade_critical) else "") == "on"
            dur_str = trade_durations[i].strip() if i < len(trade_durations) else ""
            await session.execute(sql_text(
                """INSERT INTO project_trades (project_id, trade, assigned_contact_id,
                   estimated_start, target_start, estimated_duration_days,
                   target_completion, preceding_trade, inspection_required,
                   critical_path, notes, schedule_status)
                   VALUES (:pid, :trade, :cid, :est, :tgt, :dur, :tcomp, :prec, :insp, :crit, :notes, 'estimated')"""),
                {"pid": project_id, "trade": tn,
                 "cid": trade_contacts[i].strip() if i < len(trade_contacts) and trade_contacts[i].strip() else None,
                 "est": trade_estarts[i].strip() if i < len(trade_estarts) else None,
                 "tgt": trade_tstarts[i].strip() if i < len(trade_tstarts) else None,
                 "dur": int(dur_str) if dur_str else None,
                 "tcomp": trade_tcomps[i].strip() if i < len(trade_tcomps) else None,
                 "prec": trade_preceding[i].strip() if i < len(trade_preceding) else "",
                 "insp": insp, "crit": crit,
                 "notes": trade_notes[i].strip() if i < len(trade_notes) else ""})

        await session.commit()

    return HTMLResponse("", status_code=303, headers={"Location": f"/admin/projects/{project_id}"})


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def admin_project_view(
    request: Request,
    project_id: str,
    user: dict = Depends(require_admin),
):
    """View a single project with details."""
    from sqlalchemy import text as sql_text
    async with async_session() as session:
        proj = (await session.execute(sql_text(
            "SELECT * FROM projects WHERE id = :id"
        ), {"id": project_id})).fetchone()
        if not proj:
            return HTMLResponse("Project not found", status_code=404)
        contacts = (await session.execute(sql_text(
            "SELECT c.name, c.company, c.trade, c.phone, c.email, pc.role "
            "FROM project_contacts pc JOIN contacts c ON pc.contact_id = c.id "
            "WHERE pc.project_id = :pid ORDER BY pc.assigned_at"
        ), {"pid": project_id})).fetchall()
        trades = (await session.execute(sql_text(
            "SELECT * FROM project_trades WHERE project_id = :pid ORDER BY trade"
        ), {"pid": project_id})).fetchall()
    html = _render("admin/project_view.html",
        request=request, proj=proj, contacts=contacts, trades=trades, user=user)
    return HTMLResponse(html)
