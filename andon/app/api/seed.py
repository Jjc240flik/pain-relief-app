"""
Seed endpoint — import real subcontractor contacts and house data.

Run via: curl -X POST http://localhost:8000/api/seed
or:       python -m app.api.seed
"""

import logging
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.repositories.house_repo import HouseRepository
from app.repositories.contact_repo import ContactRepository
from app.repositories.schedule_repo import ScheduleRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seed", tags=["seed"])

TRADE_PHASES = [
    "foundation_concrete", "framing", "plumbing_rough", "hvac_rough",
    "electrical_rough", "drywall_plaster", "paint", "flooring",
    "cabinets", "finish_work",
]

# ---------------------------------------------------------------------------
# Seed data based on Jimmy's interview (TLG Homes subcontractors)
# ---------------------------------------------------------------------------

SEED_CONTACTS = [
    # Foundation / Concrete
    {"trade": "foundation_concrete", "name": "Jim's Concrete", "company": "Jim's Concrete Services", "phone": "+19205551111", "email": "jim@jimsconcrete.com", "manager_phone": "+19205551212", "notes": "Used for all foundation work"},
    # Framing
    {"trade": "framing", "name": "Northwoods Framers", "company": "Northwoods Framing Co.", "phone": "+19205552222", "email": "dispatch@northwoodsframing.com", "manager_phone": "+19205552323", "notes": "Specialized framing crew — all they do is frame"},
    # Plumbing
    {"trade": "plumbing_rough", "name": "TLG Plumbing", "company": "TLG Homes Plumbing Division", "phone": "+19205553333", "email": "plumbing@tlghomes.com", "manager_phone": None, "notes": "Owned by TLG owner — newer company"},
    # HVAC
    {"trade": "hvac_rough", "name": "Mike's HVAC", "company": "Mike's Heating & Cooling", "phone": "+19205554444", "email": "mike@mikeshvac.com", "manager_phone": "+19205554545", "notes": "Been painting vent hoods himself — switching to plastic"},
    # Electrical
    {"trade": "electrical_rough", "name": "Lakeshore Electric", "company": "Lakeshore Electric LLC", "phone": "+19205555555", "email": "dispatch@lakeshoreelectric.com", "manager_phone": "+19205555656", "notes": "Electrician is also a county inspector — never fails inspection"},
    # Drywall
    {"trade": "drywall_plaster", "name": "Clint (PM Assistant)", "company": "TLG Homes", "phone": "+19205556666", "email": "clint@tlghomes.com", "manager_phone": None, "notes": "Jimmy + Clint handle small drywall touch-ups themselves"},
    # Paint
    {"trade": "paint", "name": "Paul the Painter", "company": "Paul's Painting", "phone": "+19205557777", "email": "paul@paulspainting.com", "manager_phone": "+19205557878", "notes": "Brushes trim, doesn't search for own touch-ups"},
    # Flooring
    {"trade": "flooring", "name": "Macos Flooring", "company": "Macos Flooring & Design", "phone": "+19205558888", "email": "orders@macosflooring.com", "manager_phone": "+19205558989", "notes": "Reputable — lifetime warranty, professional installers"},
    # Cabinets
    {"trade": "cabinets", "name": "Brown Building Center", "company": "Brown Building Supply", "phone": "+19205559999", "email": "builders@brownbuilding.com", "manager_phone": "+19205550000", "notes": "Supplies trim, windows, lumber packages"},
    # Finish Work
    {"trade": "finish_work", "name": "Various Finish Crews", "company": "TLG Homes", "phone": "+19205550001", "email": "finish@tlghomes.com", "manager_phone": None, "notes": "Final fixtures, touch-ups, and punch list"},
]

# Internal team contacts (not tied to a single trade)
SEED_TEAM = [
    {"trade": None, "name": "Jimmy (Project Manager)", "company": "TLG Homes", "phone": "+19205550010", "email": "jimmy@tlghomes.com", "manager_phone": None, "notes": "Project Manager — primary user of Andon system"},
    {"trade": None, "name": "Clint (Foreman)", "company": "TLG Homes", "phone": "+19205550011", "email": "clint@tlghomes.com", "manager_phone": None, "notes": "Foreman/Assistant — secondary dashboard user"},
    {"trade": None, "name": "Brian (Owner)", "company": "TLG Homes", "phone": "+19205550012", "email": "brian@tlghomes.com", "manager_phone": None, "notes": "Owner — escalations land here"},
]

SEED_HOUSES = [
    {
        "address": "1234 Lakeview Dr",
        "city": "Manitowoc",
        "state": "WI",
        "current_phase": 3,   # Plumbing rough
        "overall_status": "G",
        "notes": "Spec home — 4 bed, 2.5 bath, finished basement",
    },
    {
        "address": "5678 Shoreline Rd",
        "city": "Two Rivers",
        "state": "WI",
        "current_phase": 1,   # Foundation
        "overall_status": "G",
        "notes": "Custom home — 3 bed, 2 bath, walkout basement",
    },
    {
        "address": "9101 Forest Ave",
        "city": "Green Bay",
        "state": "WI",
        "current_phase": 6,   # Drywall
        "overall_status": "G",
        "notes": "Spec home — 5 bed, 3 bath, lake view lot",
    },
]


@router.post("")
async def seed_database(session: AsyncSession = Depends(get_db)):
    """Seed the database with contacts and houses."""
    contact_repo = ContactRepository(session)
    house_repo = HouseRepository(session)
    schedule_repo = ScheduleRepository(session)

    results = {"contacts_created": 0, "houses_created": 0, "schedules_created": 0}

    # --- Seed contacts ---
    for c in SEED_CONTACTS + SEED_TEAM:
        existing = await contact_repo.get_by_phone(c["phone"]) if c.get("phone") else None
        if not existing:
            await contact_repo.create(**c)
            results["contacts_created"] += 1

    # --- Seed houses ---
    for h in SEED_HOUSES:
        house = await house_repo.create(
            address=h["address"],
            city=h.get("city"),
            state=h.get("state", "WI"),
            current_phase=h.get("current_phase"),
            overall_status=h.get("overall_status", "G"),
            notes=h.get("notes"),
        )
        results["houses_created"] += 1
        results["schedules_created"] += await _create_sample_schedule(
            schedule_repo, house.id, h["current_phase"],
        )

    await session.commit()
    logger.info("Seed complete: %s", results)
    return {"status": "ok", "seeded": results}


async def _create_sample_schedule(
    repo: ScheduleRepository,
    house_id: UUID,
    current_phase: int | None,
) -> int:
    """Create schedule items for the given house up to its current phase."""
    count = 0
    today = date.today()

    for i, phase in enumerate(TRADE_PHASES):
        phase_num = i + 1
        if current_phase and phase_num > current_phase + 1:
            continue  # Only create items for phases up to current + 1

        scheduled_start = today + timedelta(days=(phase_num - 1) * 14)
        status = "complete" if (current_phase and phase_num < current_phase) else "scheduled"
        if current_phase and phase_num == current_phase:
            status = "in_progress"

        await repo.create(
            house_id=house_id,
            trade=phase,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_start + timedelta(days=7),
            status=status,
            andon_status="G",
            readiness_lead_days=14 if phase in ("foundation_concrete", "framing") else 7,
        )
        count += 1

    return count
