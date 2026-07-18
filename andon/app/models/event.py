from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    TIMESTAMP as TIMESTAMPTZ,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ(timezone=True), server_default=func.now(), index=True
    )
    house_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("houses.id"), nullable=True
    )
    schedule_item_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("schedule_items.id"), nullable=True
    )
    trade: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_media_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sender_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sender_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_events_ts", timestamp.desc()),
        Index("idx_events_house", "house_id", timestamp.desc()),
    )

    def __repr__(self) -> str:
        return f"<Event {self.id} direction={self.direction} channel={self.channel}>"
