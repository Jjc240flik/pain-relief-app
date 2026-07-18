from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, TIMESTAMP as TIMESTAMPTZ, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


_VALID_STATUSES = {"scheduled", "in_progress", "complete"}
_VALID_ANDON_STATUSES = {"R", "Y", "G"}


class ScheduleItem(Base):
    __tablename__ = "schedule_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    house_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("houses.id"), nullable=False
    )
    trade: Mapped[str] = mapped_column(String(30), nullable=False)
    scheduled_start: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    assigned_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    andon_status: Mapped[str] = mapped_column(String(1), default="G")
    last_touch_ts: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMPTZ(timezone=True), nullable=True
    )
    cleanup_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    readiness_lead_days: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    house: Mapped["House"] = relationship(back_populates="schedule_items")

    def __repr__(self) -> str:
        return f"<ScheduleItem {self.id} house={self.house_id} trade={self.trade}>"
