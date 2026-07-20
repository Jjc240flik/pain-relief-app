"""
Onboarding routes — new client setup wizard.

Guides new users through:
  1. Welcome / company info
  2. Add houses (projects)
  3. Import or add contacts (subcontractors)
  4. Post-setup confirmation

Accessible at /onboarding.
"""

import csv
import io
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select, text as sql_text

from app.database import async_session
from app.models.contact import Contact
from app.models.house import House
from app.repositories.base import BaseRepository
from app.repositories.house_repo import HouseRepository
from app.repositories.schedule_repo import ScheduleRepository
from app.views.dashboard import _render

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

TRADE_PHASES = [
    "foundation_concrete", "framing", "plumbing_rough", "hvac_rough",
    "electrical_rough", "drywall_plaster", "paint", "flooring",
    "cabinets", "finish_work",
]

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


async def _get_setting(key: str) -> str:
    """Get a tenant setting value."""
    async with async_session() as session:
        result = await session.execute(sql_text("SELECT value FROM tenant_settings WHERE key = :key"), {"key": key})
        row = result.fetchone()
        return row[0] if row else ""


async def _set_setting(key: str, value: str) -> None:
    """Set a tenant setting value."""
    async with async_session() as session:
        await session.execute(sql_text(
            "INSERT INTO tenant_settings (key, value) VALUES (:key, :val) "
            "ON CONFLICT (key) DO UPDATE SET value = :val"
        ), {"key": key, "val": value})
        await session.commit()


# ── Step 1: Company Info ──
@router.get("", response_class=HTMLResponse)
async def onboarding_welcome(request: Request):
    """Render the onboarding welcome / company info page."""
    company = await _get_setting("company_name")
    html = _render("onboarding/welcome.html",
        request=request,
        trades=TRADE_LABELS,
        company_name=company,
    )
    return HTMLResponse(html)


@router.post("", response_class=HTMLResponse)
async def onboarding_save_company(
    request: Request,
    company_name: str = Form(""),
):
    """Save company info and proceed to next step."""
    if company_name.strip():
        await _set_setting("company_name", company_name.strip())
    return HTMLResponse("", status_code=303, headers={"Location": "/onboarding/houses"})


# ── Step 2: Add Houses ──
@router.get("/houses", response_class=HTMLResponse)
async def onboarding_houses(request: Request):
    """Show the add-houses form."""
    company = await _get_setting("company_name")
    html = _render("onboarding/houses.html",
        request=request,
        company_name=company,
        trades=TRADE_LABELS,
    )
    return HTMLResponse(html)


@router.post("/houses", response_class=HTMLResponse)
async def onboarding_save_houses(request: Request):
    """Save houses from the form and generate schedule items."""
    form = await request.form()
    addresses = form.getlist("address")
    cities = form.getlist("city")

    async with async_session() as session:
        house_repo = HouseRepository(session)
        schedule_repo = ScheduleRepository(session)

        for i, addr in enumerate(addresses):
            addr = addr.strip()
            if not addr:
                continue
            city = cities[i].strip() if i < len(cities) else ""
            # Create the house
            house = await house_repo.create(
                address=addr,
                city=city,
                state="WI",
                current_phase=0,
                overall_status="G",
            )
            # Generate schedule items for all 10 trades
            today = date.today()
            for phase_num, trade in enumerate(TRADE_PHASES):
                await schedule_repo.create(
                    house_id=house.id,
                    trade=trade,
                    scheduled_start=today + timedelta(days=phase_num * 14),
                    scheduled_end=today + timedelta(days=phase_num * 14 + 7),
                    status="scheduled",
                    andon_status="G",
                    readiness_lead_days=14 if trade in ("foundation_concrete", "framing") else 7,
                )

        await session.commit()

    return HTMLResponse("", status_code=303, headers={"Location": "/onboarding/contacts"})


# ── Step 3: Import contacts page ──
@router.get("/contacts", response_class=HTMLResponse)
async def onboarding_import(request: Request):
    """Render the CSV import page with instructions."""
    html = _render("onboarding/import.html",
        request=request,
        error="",
        preview=None,
        trades=TRADE_LABELS,
    )
    return HTMLResponse(html)


# ── Download CSV template ──
@router.get("/template")
async def download_template():
    """Generate and download a CSV template with the correct columns."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "company", "trade", "phone", "email", "manager_phone", "notes"])
    writer.writerow(["Example Concrete Co.", "Example Concrete", "foundation_concrete", "+19205551234", "contact@example.com", "+19205551235", "Great crew"])
    writer.writerow(["Example Framing Inc.", "Example Framing", "framing", "+19205555678", "dispatch@example.com", "", "Uses own crane"])
    writer.writerow(["Example Paint LLC", "Example Paint", "paint", "+19205559012", "office@example.com", "+19205559013", ""])

    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=subcontractor_template.csv",
        },
    )


# ── Step 3: Process import ──
@router.post("/contacts", response_class=HTMLResponse)
async def onboarding_process_import(request: Request):
    """Process the uploaded CSV file and show results."""
    from app.models.contact import Contact

    form = await request.form()
    file = form.get("file")
    if not file:
        html = _render("onboarding/import.html",
            request=request, error="Please select a file to upload.",
            preview=None, trades=TRADE_LABELS,
        )
        return HTMLResponse(html)

    content = (await file.read()).decode("utf-8-sig")
    contacts = _parse_csv(content)

    if not contacts:
        html = _render("onboarding/import.html",
            request=request,
            error="No valid contacts found. Make sure your CSV has the correct columns.",
            preview=None, trades=TRADE_LABELS,
        )
        return HTMLResponse(html)

    # Import into database
    imported = 0
    updated = 0
    skipped = 0

    async with async_session() as session:
        repo = BaseRepository(session, Contact)
        for c in contacts:
            if not c["phone"] and not c["email"]:
                skipped += 1
                continue
            existing = None
            if c["phone"]:
                stmt = select(Contact).where(Contact.phone == c["phone"])
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
            if existing:
                await repo.update(existing.id, **c)
                updated += 1
            else:
                await repo.create(**c, is_active=True)
                imported += 1
        await session.commit()

    html = _render("onboarding/success.html",
        request=request,
        imported=imported,
        updated=updated,
        skipped=skipped,
        total=len(contacts),
        trades=TRADE_LABELS,
    )
    return HTMLResponse(html)


# ── Step 4: Quick add a single contact ──
@router.get("/add", response_class=HTMLResponse)
async def onboarding_add_form(request: Request):
    """Show a form to manually add a single contact."""
    html = _render("onboarding/add.html", request=request, trades=TRADE_LABELS)
    return HTMLResponse(html)


@router.post("/add", response_class=HTMLResponse)
async def onboarding_add_submit(
    request: Request,
    name: str = Form(""),
    company: str = Form(""),
    trade: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    manager_phone: str = Form(""),
    notes: str = Form(""),
):
    """Save a single manually-entered contact and redirect to add another or finish."""
    if not name.strip():
        html = _render("onboarding/add.html",
            request=request, error="Name is required.",
            trades=TRADE_LABELS,
        )
        return HTMLResponse(html)

    async with async_session() as session:
        repo = BaseRepository(session, Contact)
        await repo.create(
            name=name.strip(),
            company=company.strip(),
            trade=trade.strip(),
            phone=phone.strip(),
            email=email.strip().lower(),
            manager_phone=manager_phone.strip(),
            notes=notes.strip(),
            is_active=True,
        )
        await session.commit()

    html = _render("onboarding/success.html",
        request=request,
        imported=1, updated=0, skipped=0, total=1,
        trades=TRADE_LABELS,
    )
    return HTMLResponse(html)


# ── Step 5: Skip / go to dashboard ──
@router.get("/skip")
async def onboarding_skip():
    """Skip onboarding and go to the main dashboard."""
    return HTMLResponse("", status_code=303, headers={"Location": "/dashboard"})


# ── Helper ──
def _parse_csv(content: str) -> list[dict]:
    """Parse CSV content into contact dicts. Handles various column name formats."""
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
