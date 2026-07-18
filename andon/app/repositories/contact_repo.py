from sqlalchemy import select

from app.models.contact import Contact
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    def __init__(self, session) -> None:
        super().__init__(session, Contact)

    async def get_by_phone(self, phone: str) -> Contact | None:
        stmt = select(Contact).where(Contact.phone == phone)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_trade(self, trade: str) -> list[Contact]:
        stmt = select(Contact).where(Contact.trade == trade)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
