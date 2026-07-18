"""
Schedule management API routes.
"""

import logging
from uuid import UUID
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.schedule_repo import ScheduleRepository
from app.repositories.house_repo import HouseRepository
from app.repositories.contact_repo import ContactRepository
from app.services.outbound import OutboundService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schedule", tags=["schedule"])

TRADE_PHASES = [
    "foundation_concrete", "framing", "plumbing_rough", "hvac_rough",
    "electrical_rough", "drywall_plaster", "paint", "flooring",
    "cabinets", "finish_work",
]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ScheduleItemCreate(BaseModel):
    house_id: UUID
    trade: str = Field(..., pattern="|".join(TRADE_PHASES))
    scheduled_start: date
    scheduled_end: Optional[date] = None
    assigned_phone: Optional[str] = None
    readiness_lead_days: int = 7


class ScheduleItemUpdate(BaseModel):
    status: Optional[str] = None  # scheduled / in_progress / complete
    andon_status: Optional[str] = None  # R / Y / G
    scheduled_start: Optional[date] = None
    scheduled_end: Optional[date] = None
    assigned_phone: Optional[str] = None
    cleanup_confirmed: Optional[bool] = None


class ScheduleItemResponse(BaseModel):
    id: str
    house_id: str
    trade: str
    scheduled_start: str
    scheduled_end: str | None
    assigned_phone: str | None
    status: str
    andon_status: str
    last_touch_ts: str | None
    cleanup_confirmed: bool
    readiness_lead_days: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def list_schedule(
    house_id: Optional[UUID] = None,
    trade: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """List schedule items, optionally filtered by house_id, trade, or status."""
    repo = ScheduleRepository(session)
    if house_id:
        items = await repo.get_by_house(house_id)
    else:
        items = await repo.list(limit=200)

    if trade:
        items = [i for i in items if i.trade == trade]
    if status:
        items = [i for i in items if i.status == status]

    return [
        {
            "id": str(item.id),
            "house_id": str(item.house_id),
            "trade": item.trade,
            "scheduled_start": item.scheduled_start.isoformat(),
            "scheduled_end": item.scheduled_end.isoformat() if item.scheduled_end else None,
            "assigned_phone": item.assigned_phone,
            "status": item.status,
            "andon_status": item.andon_status,
            "last_touch_ts": item.last_touch_ts.isoformat() if item.last_touch_ts else None,
            "cleanup_confirmed": item.cleanup_confirmed,
            "readiness_lead_days": item.readiness_lead_days,
        }
        for item in items
    ]


@router.post("/")
async def create_schedule_item(
    data: ScheduleItemCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new schedule item."""
    repo = ScheduleRepository(session)
    item = await repo.create(**data.model_dump())
    await session.commit()
    return {"id": str(item.id), "status": "created"}


@router.patch("/{item_id}")
async def update_schedule_item(
    item_id: UUID,
    data: ScheduleItemUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update a schedule item (status, andon_status, dates, etc.)."""
    repo = ScheduleRepository(session)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    item = await repo.update(item_id, **update_data)
    if not item:
        raise HTTPException(status_code=404, detail="Schedule item not found")

    await session.commit()
    return {"id": str(item_id), "status": "updated"}


@router.post("/{item_id}/push")
async def push_schedule_item(
    item_id: UUID,
    days: int = 1,
    notify_next: bool = False,
    session: AsyncSession = Depends(get_db),
):
    """
    Push a schedule item by N days.

    If notify_next=True, also send SMS + email to the next trade's contact
    informing them of the new date.
    """
    repo = ScheduleRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Schedule item not found")

    # Push the dates
    update_data = {}
    if item.scheduled_start:
        update_data["scheduled_start"] = item.scheduled_start + timedelta(days=days)
    if item.scheduled_end:
        update_data["scheduled_end"] = item.scheduled_end + timedelta(days=days)
    update_data["andon_status"] = "Y"  # Pushing = at risk

    await repo.update(item_id, **update_data)
    await session.commit()

    # Notify next trade
    if notify_next:
        await _notify_next_trade(session, item, days)

    return {
        "id": str(item_id),
        "pushed_by_days": days,
        "next_trade_notified": notify_next,
    }


@router.post("/{item_id}/resolve")
async def resolve_schedule_item(
    item_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Resolve an issue — set andon_status to Green."""
    repo = ScheduleRepository(session)
    item = await repo.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Schedule item not found")

    await repo.update(item_id, andon_status="G")
    await session.commit()

    return {"id": str(item_id), "status": "resolved"}


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

async def _notify_next_trade(
    session: AsyncSession,
    current_item: "ScheduleItem",
    days_pushed: int,
) -> None:
    """Send notification to the next trade's contact about the date change."""
    trade_phases = TRADE_PHASES
    try:
        current_idx = trade_phases.index(current_item.trade)
    except ValueError:
        logger.warning("Unknown trade: %s — skipping next-trade notify", current_item.trade)
        return

    if current_idx + 1 >= len(trade_phases):
        logger.info("No next trade after %s — skipping notification", current_item.trade)
        return

    next_trade = trade_phases[current_idx + 1]
    contact_repo = ContactRepository(session)
    contacts = await contact_repo.get_by_trade(next_trade)
    if not contacts:
        logger.warning("No contacts found for next trade: %s", next_trade)
        return

    house_repo = HouseRepository(session)
    house = await house_repo.get(current_item.house_id)
    address = house.address if house else "Unknown"

    outbound = OutboundService()
    message = (
        f"TLG – Schedule update: {current_item.trade.replace('_', ' ').title()} "
        f"at {address} has been pushed {days_pushed} day(s). "
        f"Your new estimated start is {current_item.scheduled_start + timedelta(days=days_pushed)}. "
        "We'll confirm closer to the date."
    )

    # contacts is a list, send to the first one
    if contacts[0].phone:
        await outbound.send_sms(
            to_phone=contacts[0].phone,
            body=message,
            house_id=current_item.house_id,
            trade=next_trade,
        )
