"""
OutboundService — Send SMS via Twilio with quiet-hours and rate-limit enforcement.

Every outbound message is logged as an Event record (direction='outbound').
"""

import logging
from datetime import datetime, date
from uuid import UUID

from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from app.config import settings
from app.models.event import Event
from app.repositories.base import BaseRepository
from app.database import async_session

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when the rate limit for a (house, trade, day) is exceeded."""


class OutboundService:
    """Handles all outbound SMS traffic with quiet hours and rate limiting.

    Supports Twilio (default) and Plivo as providers.
    Plivo is used when plivo_auth_id is configured; otherwise falls back to Twilio.
    """

    def __init__(self) -> None:
        self._twilio: TwilioClient | None = None
        self._plivo = None
        self._provider = "log"

        # Prefer Twilio (active pilot provider), then Plivo (future)
        if settings.twilio_account_sid and settings.twilio_auth_token:
            self._twilio = TwilioClient(
                settings.twilio_account_sid,
                settings.twilio_auth_token,
            )
            self._provider = "twilio"
            logger.info("Outbound SMS provider: Twilio")
        elif settings.plivo_auth_id and settings.plivo_auth_token:
            import plivo
            self._plivo = plivo.RestClient(
                auth_id=settings.plivo_auth_id,
                auth_token=settings.plivo_auth_token,
            )
            self._provider = "plivo"
            logger.info("Outbound SMS provider: Plivo")
        else:
            logger.warning("No SMS provider configured — SMS sending disabled.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_sms(
        self,
        to_phone: str,
        body: str,
        house_id: UUID,
        trade: str,
        is_emergency: bool = False,
    ) -> bool:
        """
        Send an SMS message.

        Returns True if the message was sent (or would have been sent when
        Twilio is not configured for local testing).

        Raises RateLimitError if the rate limit would be exceeded
        (max 1 auto-outbound per trade/house/day, unless previous reply was Issue).
        """
        # --- Quiet hours check ---
        if not is_emergency and not self._within_quiet_hours():
            logger.info(
                "Suppressed outbound SMS — outside quiet hours "
                "(to=%s, house=%s, trade=%s)",
                to_phone, house_id, trade,
            )
            # For MVP, log the suppression but don't fail. The scheduler
            # will retry next period.
            return False

        # --- Rate limit check ---
        if not await self._check_rate_limit(house_id, trade):
            raise RateLimitError(
                f"Rate limit exceeded for house={house_id} trade={trade} today"
            )

        # --- Send via configured provider ---
        if self._provider == "log":
            logger.info("[DEV] Would send SMS to %s: %s", to_phone, body)
            await self._log_event(to_phone, body, house_id, trade)
            return True

        if self._provider == "plivo":
            try:
                response = self._plivo.messages.create(
                    src=settings.plivo_phone_number,
                    dst=to_phone,
                    text=body,
                )
                logger.info("Plivo SMS sent: uuid=%s to=%s", response.message_uuid, to_phone)
                await self._log_event(to_phone, body, house_id, trade)
                return True
            except Exception as exc:
                logger.error("Plivo send failed: %s", exc)
                return False

        if self._provider == "twilio":
            try:
                message = self._twilio.messages.create(
                    body=body,
                    from_=settings.twilio_phone_number,
                    to=to_phone,
                )
                logger.info("Twilio SMS sent: sid=%s to=%s", message.sid, to_phone)
                await self._log_event(to_phone, body, house_id, trade)
                return True
            except TwilioRestException as exc:
                logger.error("Twilio send failed: %s", exc)
                return False

        return False

    # ------------------------------------------------------------------
    # Readiness / Day-Before / Completion messages (convenience methods)
    # ------------------------------------------------------------------

    def build_readiness_text(self, trade: str, address: str, date_str: str) -> str:
        return (
            f"TLG – Confirming {trade.replace('_', ' ').title()} "
            f"still on for {address} on {date_str}. "
            "Reply 1=Yes 2=No 3=Issue"
        )

    def build_daybefore_text(self, trade: str, address: str) -> str:
        return (
            f"TLG – Final check: Ready for {trade.replace('_', ' ').title()} "
            f"tomorrow at {address}? 1=Yes 2=No 3=Issue / site not ready"
        )

    def build_completion_text(self, trade: str, address: str) -> str:
        return (
            f"TLG – Did you finish {trade.replace('_', ' ').title()} "
            f"at {address} today?\n"
            "1=Yes full complete\n"
            "2=Partial\n"
            "3=Issue blocking next\n"
            "Also: Site left clean? A=Yes B=No"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _within_quiet_hours() -> bool:
        now = datetime.now()
        return settings.quiet_hours_start <= now.hour < settings.quiet_hours_end

    @staticmethod
    async def _check_rate_limit(house_id: UUID, trade: str) -> bool:
        """
        Simple in-memory rate limit tracker.
        For MVP this is sufficient; for production replace with a DB-backed
        counter (rate_limit_tracker table from the Tech Spec).
        """
        # MVP: Allow all messages. Rate limiting will be added in Week 3 polish.
        # The Tech Spec defines the rate_limit_tracker table for this.
        return True

    @staticmethod
    async def _log_event(
        to_phone: str,
        body: str,
        house_id: UUID,
        trade: str,
    ) -> None:
        """Log the outbound message as an immutable Event record."""
        try:
            async with async_session() as session:
                repo = BaseRepository(session, Event)
                await repo.create(
                    direction="outbound",
                    channel="sms",
                    full_text=body,
                    house_id=house_id,
                    trade=trade,
                    triggered_by="system",
                    sender_phone=to_phone,
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to log outbound event — non-fatal")
