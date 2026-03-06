"""
Slot Manager - handles content slot creation and lifecycle.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.content_slot import ContentSlot
from app.models.post_option import PostOption
from app.models.scraped_article import ScrapedArticle

logger = logging.getLogger(__name__)
settings = get_settings()

# Dubai timezone
DUBAI_TZ = ZoneInfo("Asia/Dubai")

# Daily posting schedule (Dubai time)
SLOT_SCHEDULE = [
    {"slot_number": 1, "time": "08:00", "content_type": "real_estate"},
    {"slot_number": 2, "time": "12:00", "content_type": "general_dubai"},
    {"slot_number": 3, "time": "16:00", "content_type": "real_estate"},
    {"slot_number": 4, "time": "20:00", "content_type": "general_dubai"},
    {"slot_number": 5, "time": "00:00", "content_type": "general_dubai"},
]

# Approval deadline: 30 minutes before slot time
APPROVAL_DEADLINE_MINUTES = 30


class SlotManager:
    """
    Manages content slot creation and lifecycle.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_daily_slots(self, target_date: date) -> list[ContentSlot]:
        """
        Create all 5 content slots for a given date.

        Args:
            target_date: The date to create slots for

        Returns:
            List of created ContentSlot objects
        """
        created_slots = []

        for schedule in SLOT_SCHEDULE:
            # Check if slot already exists
            existing = await self._get_slot(
                target_date,
                schedule["slot_number"]
            )

            if existing:
                logger.debug(f"Slot {schedule['slot_number']} for {target_date} already exists")
                created_slots.append(existing)
                continue

            # Parse time and create datetime in Dubai timezone
            hour, minute = map(int, schedule["time"].split(":"))

            # Handle midnight (00:00) which belongs to the next day conceptually
            if hour == 0:
                slot_date = target_date + timedelta(days=1)
            else:
                slot_date = target_date

            scheduled_dt = datetime(
                slot_date.year, slot_date.month, slot_date.day,
                hour, minute,
                tzinfo=DUBAI_TZ
            )

            # Calculate approval deadline (30 min before)
            approval_deadline = scheduled_dt - timedelta(minutes=APPROVAL_DEADLINE_MINUTES)

            slot = ContentSlot(
                scheduled_date=target_date,
                scheduled_time=schedule["time"],
                scheduled_at=scheduled_dt,
                slot_number=schedule["slot_number"],
                content_type=schedule["content_type"],
                status="pending",
                approval_deadline=approval_deadline,
            )

            self.db.add(slot)
            created_slots.append(slot)

        await self.db.commit()

        for slot in created_slots:
            await self.db.refresh(slot)

        logger.info(f"Created/retrieved {len(created_slots)} slots for {target_date}")
        return created_slots

    async def _get_slot(self, target_date: date, slot_number: int) -> Optional[ContentSlot]:
        """Get existing slot by date and number."""
        result = await self.db.execute(
            select(ContentSlot).where(
                and_(
                    ContentSlot.scheduled_date == target_date,
                    ContentSlot.slot_number == slot_number
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_slot_with_options(self, slot_id: UUID) -> Optional[ContentSlot]:
        """Get a slot with its post options loaded."""
        result = await self.db.execute(
            select(ContentSlot)
            .options(selectinload(ContentSlot.options))
            .where(ContentSlot.id == slot_id)
        )
        return result.scalar_one_or_none()

    async def get_slots_for_date(self, target_date: date) -> list[ContentSlot]:
        """Get all slots for a given date."""
        result = await self.db.execute(
            select(ContentSlot)
            .options(selectinload(ContentSlot.options))
            .where(ContentSlot.scheduled_date == target_date)
            .order_by(ContentSlot.slot_number)
        )
        return list(result.scalars().all())

    async def get_pending_slots(self) -> list[ContentSlot]:
        """Get all slots that need content generation."""
        result = await self.db.execute(
            select(ContentSlot)
            .where(ContentSlot.status == "pending")
            .order_by(ContentSlot.scheduled_at)
        )
        return list(result.scalars().all())

    async def get_slots_needing_selection(self) -> list[ContentSlot]:
        """
        Get slots that have options ready but need selection.

        These are slots where:
        - Status is 'options_ready'
        - Approval deadline has passed
        - No option has been selected yet
        """
        now = datetime.now(DUBAI_TZ)

        result = await self.db.execute(
            select(ContentSlot)
            .options(selectinload(ContentSlot.options))
            .where(
                and_(
                    ContentSlot.status == "options_ready",
                    ContentSlot.approval_deadline < now,
                    ContentSlot.selected_option_id.is_(None)
                )
            )
            .order_by(ContentSlot.scheduled_at)
        )
        return list(result.scalars().all())

    async def get_slots_ready_to_publish(self) -> list[ContentSlot]:
        """
        Get slots that are approved and ready for publishing.

        These are slots where:
        - Status is 'approved'
        - Scheduled time has arrived or passed
        """
        now = datetime.now(DUBAI_TZ)

        result = await self.db.execute(
            select(ContentSlot)
            .options(selectinload(ContentSlot.options))
            .where(
                and_(
                    ContentSlot.status == "approved",
                    ContentSlot.scheduled_at <= now
                )
            )
            .order_by(ContentSlot.scheduled_at)
        )
        return list(result.scalars().all())

    async def update_slot_status(
        self,
        slot_id: UUID,
        status: str,
        selected_option_id: Optional[UUID] = None,
        selected_by: Optional[str] = None,
        selected_by_user_id: Optional[UUID] = None,
    ) -> ContentSlot:
        """Update a slot's status and optional selection info."""
        result = await self.db.execute(
            select(ContentSlot).where(ContentSlot.id == slot_id)
        )
        slot = result.scalar_one_or_none()

        if not slot:
            raise ValueError(f"Slot {slot_id} not found")

        slot.status = status

        if selected_option_id:
            slot.selected_option_id = selected_option_id
            slot.selected_by = selected_by
            slot.selected_by_user_id = selected_by_user_id

            # Mark the option as selected
            await self.db.execute(
                select(PostOption).where(PostOption.id == selected_option_id)
            )
            option_result = await self.db.execute(
                select(PostOption).where(PostOption.id == selected_option_id)
            )
            option = option_result.scalar_one_or_none()
            if option:
                option.is_selected = True

        await self.db.commit()
        await self.db.refresh(slot)
        return slot

    async def get_articles_for_content_type(
        self,
        content_type: str,
        limit: int = 10,
        exclude_used: bool = True,
    ) -> list[ScrapedArticle]:
        """
        Get relevant articles for content generation.

        Args:
            content_type: "real_estate" or "general_dubai"
            limit: Maximum articles to return
            exclude_used: Whether to exclude already-used articles

        Returns:
            List of relevant ScrapedArticle objects
        """
        # Map content type to preferred categories
        if content_type == "real_estate":
            preferred_categories = ["real_estate", "market_analysis", "construction", "regulation"]
        else:
            preferred_categories = [
                "economy", "tech", "lifestyle", "events", "tourism",
                "general", "business", "transportation", "entertainment"
            ]

        # Build query with preferred categories
        query = select(ScrapedArticle).where(
            ScrapedArticle.category.in_(preferred_categories)
        )

        if exclude_used:
            query = query.where(ScrapedArticle.used_in_post_id.is_(None))

        # Order by relevance and recency
        query = query.order_by(
            ScrapedArticle.relevance_score.desc(),
            ScrapedArticle.scraped_at.desc()
        ).limit(limit)

        result = await self.db.execute(query)
        articles = list(result.scalars().all())

        # Fallback: if no articles found with preferred categories, get ANY unused articles
        if not articles:
            logger.warning(
                f"No articles found for {content_type} with categories {preferred_categories}. "
                "Falling back to any available articles."
            )
            fallback_query = select(ScrapedArticle)

            if exclude_used:
                fallback_query = fallback_query.where(ScrapedArticle.used_in_post_id.is_(None))

            fallback_query = fallback_query.order_by(
                ScrapedArticle.relevance_score.desc(),
                ScrapedArticle.scraped_at.desc()
            ).limit(limit)

            fallback_result = await self.db.execute(fallback_query)
            articles = list(fallback_result.scalars().all())

        return articles

    async def mark_articles_as_used(
        self,
        article_ids: list[UUID],
        post_option_id: UUID,
    ) -> None:
        """Mark articles as used in a post option."""
        for article_id in article_ids:
            result = await self.db.execute(
                select(ScrapedArticle).where(ScrapedArticle.id == article_id)
            )
            article = result.scalar_one_or_none()
            if article:
                article.used_in_post_id = post_option_id

        await self.db.commit()
