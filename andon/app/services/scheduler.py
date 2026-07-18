"""
SchedulerService — APScheduler-based job manager for outbound messaging.

Jobs (run daily):
  1. Readiness Check — send readiness texts to subs whose scheduled_start is
     within their readiness_lead_days window
  2. Day-Before Confirmation — send day-before texts
  3. (Future) Completion Check — send end-of-day completion texts
  4. (Future) Midpoint Check — extra confirmation during foundation/framing windows
"""

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.house import House
from app.models.schedule_item import ScheduleItem
from app.models.contact import Contact
from app.repositories.schedule_repo import ScheduleRepository
from app.repositories.contact_repo import ContactRepository
from app.services.outbound import OutboundService

logger = logging.getLogger(__name__)

# Central timezone for quiet hours and scheduling
TZ = ZoneInfo("America/Chicago")

# Trades that get extended readiness windows
LONG_LEAD_TRADES = {"foundation_concrete", "framing"}
MID_LEAD_TRADES = {"plumbing_rough", "hvac_rough", "electrical_rough"}
SHORT_LEAD_TRADES = {"drywall_plaster", "paint", "flooring", "cabinets", "finish_work"}


class SchedulerService:
    """Manages APScheduler jobs for recurring outbound messaging."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone=TZ)
        self._outbound = OutboundService()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Register all recurring jobs and start the scheduler."""
        # Run readiness checks daily at 6:00 AM (before quiet hours open at 7)
        self._scheduler.add_job(
            self.run_readiness_checks,
            CronTrigger(hour=6, minute=0, timezone=TZ),
            id="readiness_checks",
            replace_existing=True,
        )

        # Run day-before confirmations daily at 7:00 AM
        self._scheduler.add_job(
            self.run_day_before_confirmations,
            CronTrigger(hour=7, minute=0, timezone=TZ),
            id="day_before_confirmations",
            replace_existing=True,
        )

        # Run completion checks daily at 3:00 PM
        self._scheduler.add_job(
            self.run_completion_checks,
            CronTrigger(hour=15, minute=0, timezone=TZ),
            id="completion_checks",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("Scheduler started with readiness, day-before, and completion jobs.")

    def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

    # ------------------------------------------------------------------
    # Scheduled jobs
    # ------------------------------------------------------------------

    async def run_readiness_checks(self) -> None:
        """
        Find schedule_items whose start date is within their readiness window
        and send a confirmation text to the assigned sub.
        """
        logger.info("Running readiness checks...")
        today = date.today()

        async with async_session() as session:
            schedule_repo = ScheduleRepository(session)
            contact_repo = ContactRepository(session)

            due = await schedule_repo.get_due_for_readiness()
            logger.info("Found %d items due for readiness check.", len(due))

            for item in due:
                # Find the contact for this trade
                contacts = await contact_repo.get_by_trade(item.trade)
                if not contacts:
                    logger.warning(
                        "No contact found for trade=%s house=%s — skipping",
                        item.trade, item.house_id,
                    )
                    continue

                contact = contacts[0]
                if not contact.phone:
                    logger.warning(
                        "Contact %s has no phone — skipping readiness check",
                        contact.name,
                    )
                    continue

                # Get house address
                house = await session.get(House, item.house_id)
                address = house.address if house else "Unknown"

                # Build and send message
                text = self._outbound.build_readiness_text(
                    item.trade, address, item.scheduled_start.isoformat(),
                )
                success = await self._outbound.send_sms(
                    to_phone=contact.phone,
                    body=text,
                    house_id=item.house_id,
                    trade=item.trade,
                )
                if success:
                    logger.info(
                        "Readiness check sent: trade=%s house=%s contact=%s",
                        item.trade, item.house_id, contact.name,
                    )
                else:
                    logger.warning(
                        "Readiness check failed to send: trade=%s house=%s",
                        item.trade, item.house_id,
                    )

    async def run_day_before_confirmations(self) -> None:
        """
        Send day-before confirmation texts for items starting tomorrow.
        """
        logger.info("Running day-before confirmations...")
        tomorrow = date.today() + timedelta(days=1)

        async with async_session() as session:
            schedule_repo = ScheduleRepository(session)
            contact_repo = ContactRepository(session)

            # Query items starting tomorrow
            stmt = select(ScheduleItem).where(
                ScheduleItem.scheduled_start == tomorrow,
                ScheduleItem.status == "scheduled",
                ScheduleItem.andon_status == "G",
            )
            result = await session.execute(stmt)
            items = result.scalars().all()

            logger.info("Found %d items due for day-before confirmation.", len(items))

            for item in items:
                contacts = await contact_repo.get_by_trade(item.trade)
                if not contacts or not contacts[0].phone:
                    continue
                contact = contacts[0]

                house = await session.get(House, item.house_id)
                address = house.address if house else "Unknown"

                text = self._outbound.build_daybefore_text(item.trade, address)
                success = await self._outbound.send_sms(
                    to_phone=contact.phone,
                    body=text,
                    house_id=item.house_id,
                    trade=item.trade,
                )
                if success:
                    logger.info(
                        "Day-before sent: trade=%s house=%s", item.trade, item.house_id,
                    )

    async def run_completion_checks(self) -> None:
        """
        Send end-of-day completion checks for items marked in_progress.
        """
        logger.info("Running completion checks...")
        today = date.today()

        async with async_session() as session:
            schedule_repo = ScheduleRepository(session)
            contact_repo = ContactRepository(session)

            stmt = select(ScheduleItem).where(
                ScheduleItem.status == "in_progress",
            )
            result = await session.execute(stmt)
            items = result.scalars().all()

            logger.info("Found %d items due for completion check.", len(items))

            for item in items:
                contacts = await contact_repo.get_by_trade(item.trade)
                if not contacts or not contacts[0].phone:
                    continue
                contact = contacts[0]

                house = await session.get(House, item.house_id)
                address = house.address if house else "Unknown"

                text = self._outbound.build_completion_text(item.trade, address)
                success = await self._outbound.send_sms(
                    to_phone=contact.phone,
                    body=text,
                    house_id=item.house_id,
                    trade=item.trade,
                )
                if success:
                    logger.info(
                        "Completion check sent: trade=%s house=%s", item.trade, item.house_id,
                    )
