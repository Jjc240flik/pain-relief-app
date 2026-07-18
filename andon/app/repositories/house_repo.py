from uuid import UUID

from sqlalchemy import select

from app.models.house import House
from app.repositories.base import BaseRepository


class HouseRepository(BaseRepository[House]):
    def __init__(self, session) -> None:
        super().__init__(session, House)

    async def get_by_status(self, status: str) -> list[House]:
        stmt = select(House).where(House.overall_status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active(self) -> list[House]:
        stmt = select(House).where(House.overall_status.in_(["R", "Y"]))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
