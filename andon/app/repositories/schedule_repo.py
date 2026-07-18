from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select, and_

from app.models.schedule_item import ScheduleItem
from app.repositories.base import BaseRepository


class ScheduleRepository(BaseRepository[ScheduleItem]):
    def __init__(self, session) -> None:
        super().__init__(session, ScheduleItem)

    async def get_by_house(self, house_id: UUID) -> list[ScheduleItem]:
        stmt = select(ScheduleItem).where(ScheduleItem.house_id == house_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_trade_and_house(
        self, house_id: UUID, trade: str
    ) -> ScheduleItem | None:
        stmt = select(ScheduleItem).where(
            and_(
                ScheduleItem.house_id == house_id,
                ScheduleItem.trade == trade,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_upcoming(self, days: int = 14) -> list[ScheduleItem]:
        cutoff = date.today() + timedelta(days=days)
        stmt = select(ScheduleItem).where(
            ScheduleItem.scheduled_start <= cutoff
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_due_for_readiness(self) -> list[ScheduleItem]:
        today = date.today()
        stmt = select(ScheduleItem).where(
            and_(
                ScheduleItem.scheduled_start - ScheduleItem.readiness_lead_days <= today,
                ScheduleItem.andon_status == "G",
                ScheduleItem.status == "scheduled",
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
