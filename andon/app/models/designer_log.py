from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, TIMESTAMP as TIMESTAMPTZ, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DesignerForwardingLog(Base):
    __tablename__ = "designer_forwarding_log"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )
    house_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("houses.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    designer_contact_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    forwarded_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ(timezone=True), server_default=func.now()
    )
    answered_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMPTZ(timezone=True), nullable=True
    )
    fallback_to_pm: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<DesignerForwardingLog {self.id} event={self.event_id}>"
