from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Integer, String, Text, TIMESTAMP as TIMESTAMPTZ, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.schedule_item import ScheduleItem


class House(Base):
    __tablename__ = "houses"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    address: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, default="WI")
    current_phase: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overall_status: Mapped[str] = mapped_column(
        String(1), default="G"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    schedule_items: Mapped[list["ScheduleItem"]] = relationship(
        back_populates="house", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<House {self.id} {self.address}>"
