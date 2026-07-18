"""
InboundProcessor — Orchestrates the full inbound message pipeline.

Pipeline:
  1. Identify sender (resolve phone/email → contact → trade)
  2. Transcribe if voice (placeholder — voice MVP in Phase 2)
  3. Detect house + trade context
  4. Classify message
  5. Update schedule_item.andon_status
  6. Insert immutable Event record
  7. Apply side effects (notifications, designer forwarding)
"""

import logging
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.contact_repo import ContactRepository
from app.repositories.schedule_repo import ScheduleRepository
from app.repositories.house_repo import HouseRepository
from app.repositories.base import BaseRepository
from app.models.event import Event
from app.services.classifier import ClassifierEngine

logger = logging.getLogger(__name__)


class InboundProcessor:
    """Processes inbound messages from any channel."""

    def __init__(self, classifier: ClassifierEngine) -> None:
        self._classifier = classifier

    async def process(
        self,
        session: AsyncSession,
        channel: str,
        sender_id: str,            # phone number (E.164) or email
        raw_text: str | None,
        audio_url: str | None = None,
        raw_payload: dict | None = None,
    ) -> dict:
        """
        Process an inbound message.

        Returns a result dict with keys:
          - handled: bool
          - status_change: str | None (R/Y/G)
          - selections: bool
          - contact_name: str | None
          - house_address: str | None
          - event_id: str | None
        """
        result = {
            "handled": False,
            "status_change": None,
            "selections": False,
            "contact_name": None,
            "house_address": None,
            "event_id": None,
        }

        # --- Step 1: Identify sender ---
        contact_repo = ContactRepository(session)
        contact = None
        if channel == "sms" and sender_id:
            contact = await contact_repo.get_by_phone(sender_id)

        if contact:
            result["contact_name"] = contact.name
            logger.info("Identified sender: %s (%s)", contact.name, contact.phone)
        else:
            logger.info("Unknown sender: %s — logging to review queue", sender_id)
            # Still log the event for the review queue
            await self._log_event(
                session, channel, sender_id, raw_text or "",
                audio_url, None, None, None, raw_payload,
            )
            await session.commit()
            result["handled"] = True  # We captured it; human reviews later
            return result

        # --- Step 2: Transcribe (placeholder — Phase 2) ---
        full_text = raw_text or ""
        confidence = 1.0
        if audio_url:
            # TODO: Phase 2 — call Whisper API, store transcript + confidence
            full_text = "[Voice message — transcription pending]"
            confidence = 0.0

        # --- Step 3: Detect house + trade context ---
        house, schedule_item = await self._resolve_context(
            session, sender_id, full_text, contact.trade,
        )
        if house:
            result["house_address"] = house.address
        house_id = house.id if house else None
        schedule_id = schedule_item.id if schedule_item else None
        trade = schedule_item.trade if schedule_item else contact.trade

        # --- Step 4: Classify ---
        cls_result = self._classifier.classify(full_text)
        logger.info(
            "Classification: status=%s conf=%.2f selections=%s keyword=%s reply=%s",
            cls_result.andon_status, cls_result.confidence,
            cls_result.is_selections_query,
            cls_result.matched_keyword,
            cls_result.structured_reply,
        )

        # --- Step 5: Update schedule item status ---
        if cls_result.andon_status and schedule_item:
            schedule_item.andon_status = cls_result.andon_status
            schedule_item.last_touch_ts = __import__("datetime").datetime.now()
            session.add(schedule_item)
            result["status_change"] = cls_result.andon_status

            # --- Step 5b: Update house overall_status ---
            if house:
                house.overall_status = cls_result.andon_status
                session.add(house)

        # --- Step 6: Log immutable Event ---
        event = await self._log_event(
            session, channel, sender_id, full_text, audio_url,
            house_id, schedule_id, trade,
            raw_payload, cls_result, contact.name if contact else "unknown",
        )
        result["event_id"] = str(event.id) if event else None

        # --- Step 7: Side effects ---
        # Selections forwarding
        if cls_result.is_selections_query and house and full_text:
            await self._handle_selections(session, event, house, full_text)
            result["selections"] = True

        # Red notifications
        if cls_result.andon_status == 'R' and house and schedule_item:
            await self._notify_red(house.address, trade, full_text, schedule_item)

        await session.commit()
        result["handled"] = True
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _resolve_context(
        session: AsyncSession,
        sender_id: str,
        text: str,
        contact_trade: str | None,
    ):
        """
        Determine which house and schedule_item this message relates to.

        Strategy for MVP:
          1. Try to extract an address (or part of it) from the message text.
          2. Fall back to the sender's most recent active schedule item
             matching their trade.
        """
        from app.models.house import House

        schedule_repo = ScheduleRepository(session)
        house_repo = HouseRepository(session)
        houses = await house_repo.list(limit=50)

        # Try: check if any house address appears in the message text
        text_lower = text.lower()
        for h in houses:
            if h.address.lower() in text_lower:
                # Found the house — now find the best matching schedule
                scheds = await schedule_repo.get_by_house(h.id)
                # Prefer a schedule matching the contact's trade
                if contact_trade:
                    for s in scheds:
                        if s.trade == contact_trade and s.status in ("scheduled", "in_progress"):
                            return h, s
                # Fall back to the first in_progress or scheduled item
                for s in scheds:
                    if s.status in ("scheduled", "in_progress"):
                        return h, s
                return h, None

        # Fallback: find the most recent active schedule for the contact's trade
        if contact_trade:
            for h in houses:
                scheds = await schedule_repo.get_by_house(h.id)
                for s in scheds:
                    if s.trade == contact_trade and s.status in ("scheduled", "in_progress"):
                        return h, s

        return None, None

    @staticmethod
    async def _log_event(
        session: AsyncSession,
        channel: str,
        sender_id: str,
        full_text: str,
        audio_url: str | None,
        house_id: UUID | None,
        schedule_item_id: UUID | None,
        trade: str | None,
        raw_payload: dict | None,
        cls_result: "ClassificationResult | None" = None,
        sender_name: str = "unknown",
    ) -> Event:
        repo = BaseRepository(session, Event)
        event = await repo.create(
            direction="inbound",
            channel=channel,
            full_text=full_text,
            original_media_url=audio_url,
            house_id=house_id,
            schedule_item_id=schedule_item_id,
            trade=trade,
            outcome=cls_result.andon_status if cls_result else None,
            triggered_by="sub",
            confidence_score=cls_result.confidence if cls_result else None,
            sender_phone=sender_id if channel in ("sms", "phone_call") else None,
            sender_email=sender_id if channel == "email" else None,
            raw_payload=raw_payload,
        )
        return event

    @staticmethod
    async def _handle_selections(
        session: AsyncSession,
        event: Event,
        house: "House",
        text: str,
    ) -> None:
        """Forward selections query to designer via SMS (or fallback to Jim)."""
        from app.models.designer_log import DesignerForwardingLog

        designer_phone = settings.designer_phone_number or settings.jim_phone_number
        if designer_phone:
            # TODO: Phase 3 — actually send SMS to designer via OutboundService
            logger.info(
                "[DESIGNER FWD] Would forward to %s: House=%s Query=%s",
                designer_phone, house.address, text,
            )

        log_entry = DesignerForwardingLog(
            event_id=event.id,
            house_id=house.id,
            question=text,
            fallback_to_pm=not bool(settings.designer_phone_number),
        )
        session.add(log_entry)

    @staticmethod
    async def _notify_red(
        address: str, trade: str, text: str, schedule_item: "ScheduleItem",
    ) -> None:
        """Send Red alert notifications — breaks quiet hours."""
        logger.info(
            "[RED ALERT] House=%s Trade=%s Message=%s",
            address, trade, text,
        )
        # TODO: Phase 2 — actually send SMS to Jim via OutboundService
        # This call would use OutboundService.send_sms with is_emergency=True
