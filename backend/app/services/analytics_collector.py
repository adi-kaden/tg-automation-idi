"""
Analytics Collector Service.

Collects engagement metrics from Telegram for published posts and channel stats.

Note: The Telegram Bot API has limited access to message statistics.
- Subscriber count: Available via getChat
- Message views: Not available via Bot API (would need MTProto/Telethon)
- Reactions: Available for messages in groups/channels where bot is admin

For production use, consider:
1. Using Telegram's native channel statistics (channel owner only)
2. Implementing MTProto client for full stats access
3. Manual data entry for view counts
"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional
from uuid import UUID

from telegram import Bot
from telegram.error import TelegramError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ChannelStats:
    """Channel-level statistics."""
    subscriber_count: int
    title: str
    username: Optional[str]
    description: Optional[str]


@dataclass
class PostStats:
    """Post-level statistics."""
    message_id: int
    views: int = 0
    forwards: int = 0
    replies: int = 0
    reactions: dict = None

    def __post_init__(self):
        if self.reactions is None:
            self.reactions = {}


class AnalyticsCollector:
    """
    Collect analytics from Telegram.

    Limitations:
    - Bot API doesn't expose view counts for channel messages
    - Reactions available only if bot has appropriate permissions
    - For full analytics, use MTProto API (Telethon/Pyrogram)
    """

    def __init__(self):
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not configured")
        if not settings.telegram_channel_id:
            raise ValueError("TELEGRAM_CHANNEL_ID not configured")

        self.bot = Bot(token=settings.telegram_bot_token)
        self.channel_id = settings.telegram_channel_id

    async def get_channel_stats(self) -> Optional[ChannelStats]:
        """
        Get current channel statistics.

        Returns:
            ChannelStats with subscriber count and channel info
        """
        try:
            chat = await self.bot.get_chat(self.channel_id)

            # member_count may not be available for all channel types
            subscriber_count = getattr(chat, "member_count", None)
            if subscriber_count is None:
                # Try to get member count explicitly
                try:
                    count = await self.bot.get_chat_member_count(self.channel_id)
                    subscriber_count = count
                except TelegramError:
                    subscriber_count = 0

            return ChannelStats(
                subscriber_count=subscriber_count,
                title=chat.title or "",
                username=chat.username,
                description=chat.description,
            )

        except TelegramError as e:
            logger.error(f"Failed to get channel stats: {e}")
            return None

    async def get_post_stats(self, message_id: int) -> Optional[PostStats]:
        """
        Get statistics for a specific post.

        Note: Bot API doesn't provide view counts for channel messages.
        This method returns what's available (reactions if accessible).

        Args:
            message_id: Telegram message ID

        Returns:
            PostStats with available metrics
        """
        try:
            # Note: Bot API doesn't have a direct method to get message stats
            # We can only copy/forward messages, not read their stats
            # Reactions are also not directly accessible via standard Bot API

            # Return placeholder - in production, this would need:
            # 1. MTProto client (Telethon/Pyrogram) for full stats
            # 2. Webhook to receive updates about reactions
            # 3. Manual entry mechanism

            logger.debug(f"Post stats requested for message {message_id} - Bot API limitations apply")

            return PostStats(
                message_id=message_id,
                views=0,  # Not available via Bot API
                forwards=0,  # Not available via Bot API
                replies=0,  # Would need to track separately
                reactions={},  # Would need webhook or MTProto
            )

        except TelegramError as e:
            logger.error(f"Failed to get post stats for message {message_id}: {e}")
            return None

    def calculate_engagement_rate(
        self,
        views: int,
        forwards: int,
        replies: int,
        reactions_total: int,
    ) -> float:
        """
        Calculate engagement rate.

        Formula: (forwards + replies + reactions) / views * 100

        Args:
            views: Number of views
            forwards: Number of forwards
            replies: Number of replies
            reactions_total: Total reaction count

        Returns:
            Engagement rate as percentage (0-100)
        """
        if views == 0:
            return 0.0

        engagement = forwards + replies + reactions_total
        return round((engagement / views) * 100, 2)

    async def collect_all_post_analytics(
        self,
        db_session,
        hours_back: int = 48,
    ) -> dict:
        """
        Collect analytics for recent published posts.

        Args:
            db_session: Database session
            hours_back: How far back to look for posts

        Returns:
            Summary of collection results
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.published_post import PublishedPost
        from app.models.post_analytics import PostAnalytics

        cutoff = datetime.utcnow() - timedelta(hours=hours_back)

        # Get recent published posts
        result = await db_session.execute(
            select(PublishedPost)
            .options(selectinload(PublishedPost.analytics))
            .where(PublishedPost.published_at >= cutoff)
        )
        posts = result.scalars().all()

        updated = 0
        created = 0
        errors = 0

        for post in posts:
            if not post.telegram_message_id:
                continue

            try:
                stats = await self.get_post_stats(post.telegram_message_id)
                if not stats:
                    errors += 1
                    continue

                # Calculate total reactions
                reactions_total = sum(stats.reactions.values()) if stats.reactions else 0

                # Calculate engagement rate
                engagement_rate = self.calculate_engagement_rate(
                    views=stats.views,
                    forwards=stats.forwards,
                    replies=stats.replies,
                    reactions_total=reactions_total,
                )

                if post.analytics:
                    # Update existing analytics
                    analytics = post.analytics

                    # Store previous values for growth calculation
                    prev_views = analytics.views

                    analytics.views = stats.views
                    analytics.forwards = stats.forwards
                    analytics.replies = stats.replies
                    analytics.reactions = json.dumps(stats.reactions) if stats.reactions else None
                    analytics.engagement_rate = engagement_rate
                    analytics.last_fetched_at = datetime.utcnow()

                    # Calculate view growth (if we have previous data)
                    if prev_views > 0 and stats.views > 0:
                        analytics.view_growth_1h = round(
                            ((stats.views - prev_views) / prev_views) * 100, 2
                        )

                    # Append to hourly snapshots
                    snapshots = []
                    if analytics.hourly_snapshots:
                        try:
                            snapshots = json.loads(analytics.hourly_snapshots)
                        except json.JSONDecodeError:
                            snapshots = []

                    snapshots.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "views": stats.views,
                        "forwards": stats.forwards,
                        "reactions": reactions_total,
                    })

                    # Keep only last 48 snapshots (48 hours at hourly intervals)
                    analytics.hourly_snapshots = json.dumps(snapshots[-48:])

                    updated += 1
                else:
                    # Create new analytics record
                    analytics = PostAnalytics(
                        post_id=post.id,
                        views=stats.views,
                        forwards=stats.forwards,
                        replies=stats.replies,
                        reactions=json.dumps(stats.reactions) if stats.reactions else None,
                        engagement_rate=engagement_rate,
                        hourly_snapshots=json.dumps([{
                            "timestamp": datetime.utcnow().isoformat(),
                            "views": stats.views,
                            "forwards": stats.forwards,
                            "reactions": reactions_total,
                        }]),
                    )
                    db_session.add(analytics)
                    created += 1

            except Exception as e:
                logger.error(f"Failed to collect analytics for post {post.id}: {e}")
                errors += 1

        await db_session.commit()

        return {
            "posts_processed": len(posts),
            "updated": updated,
            "created": created,
            "errors": errors,
        }

    async def create_daily_snapshot(self, db_session, snapshot_date: date = None) -> dict:
        """
        Create a daily channel snapshot.

        Args:
            db_session: Database session
            snapshot_date: Date for snapshot (defaults to today)

        Returns:
            Snapshot data
        """
        from sqlalchemy import select, func
        from app.models.channel_snapshot import ChannelSnapshot
        from app.models.published_post import PublishedPost
        from app.models.post_analytics import PostAnalytics

        if not snapshot_date:
            snapshot_date = date.today()

        # Check if snapshot already exists
        existing = await db_session.execute(
            select(ChannelSnapshot).where(ChannelSnapshot.snapshot_date == snapshot_date)
        )
        if existing.scalar_one_or_none():
            logger.info(f"Snapshot for {snapshot_date} already exists")
            return {"status": "exists", "date": str(snapshot_date)}

        # Get channel stats
        channel_stats = await self.get_channel_stats()
        subscriber_count = channel_stats.subscriber_count if channel_stats else 0

        # Get previous day's snapshot for growth calculation
        prev_date = snapshot_date - timedelta(days=1)
        prev_result = await db_session.execute(
            select(ChannelSnapshot).where(ChannelSnapshot.snapshot_date == prev_date)
        )
        prev_snapshot = prev_result.scalar_one_or_none()
        subscriber_growth = 0
        if prev_snapshot:
            subscriber_growth = subscriber_count - prev_snapshot.subscriber_count

        # Count posts published on this date
        posts_result = await db_session.execute(
            select(func.count(PublishedPost.id))
            .where(func.date(PublishedPost.published_at) == snapshot_date)
        )
        posts_published = posts_result.scalar() or 0

        # Calculate average views and engagement for posts on this date
        analytics_result = await db_session.execute(
            select(
                func.avg(PostAnalytics.views),
                func.avg(PostAnalytics.engagement_rate),
            )
            .join(PublishedPost)
            .where(func.date(PublishedPost.published_at) == snapshot_date)
        )
        row = analytics_result.one_or_none()
        avg_views = row[0] if row and row[0] else 0.0
        avg_engagement = row[1] if row and row[1] else 0.0

        # Find top post (highest views) for the date
        top_post_result = await db_session.execute(
            select(PostAnalytics.post_id)
            .join(PublishedPost)
            .where(func.date(PublishedPost.published_at) == snapshot_date)
            .order_by(PostAnalytics.views.desc())
            .limit(1)
        )
        top_post_row = top_post_result.one_or_none()
        top_post_id = top_post_row[0] if top_post_row else None

        # Create snapshot
        snapshot = ChannelSnapshot(
            snapshot_date=snapshot_date,
            subscriber_count=subscriber_count,
            subscriber_growth=subscriber_growth,
            posts_published=posts_published,
            avg_views=float(avg_views),
            avg_engagement_rate=float(avg_engagement),
            top_post_id=top_post_id,
        )
        db_session.add(snapshot)
        await db_session.commit()

        logger.info(f"Created channel snapshot for {snapshot_date}: {subscriber_count} subscribers")

        return {
            "status": "created",
            "date": str(snapshot_date),
            "subscriber_count": subscriber_count,
            "subscriber_growth": subscriber_growth,
            "posts_published": posts_published,
            "avg_views": avg_views,
            "avg_engagement_rate": avg_engagement,
        }

    async def get_analytics_summary(self, db_session, days: int = 7) -> dict:
        """
        Get analytics summary for the dashboard.

        Args:
            db_session: Database session
            days: Number of days to include

        Returns:
            Summary statistics
        """
        from sqlalchemy import select, func
        from app.models.channel_snapshot import ChannelSnapshot
        from app.models.published_post import PublishedPost
        from app.models.post_analytics import PostAnalytics

        cutoff_date = date.today() - timedelta(days=days)

        # Get latest channel snapshot
        latest_snapshot_result = await db_session.execute(
            select(ChannelSnapshot)
            .order_by(ChannelSnapshot.snapshot_date.desc())
            .limit(1)
        )
        latest_snapshot = latest_snapshot_result.scalar_one_or_none()

        # Get total posts in period
        posts_count_result = await db_session.execute(
            select(func.count(PublishedPost.id))
            .where(func.date(PublishedPost.published_at) >= cutoff_date)
        )
        total_posts = posts_count_result.scalar() or 0

        # Get total views in period
        views_result = await db_session.execute(
            select(func.sum(PostAnalytics.views))
            .join(PublishedPost)
            .where(func.date(PublishedPost.published_at) >= cutoff_date)
        )
        total_views = views_result.scalar() or 0

        # Get average engagement
        avg_engagement_result = await db_session.execute(
            select(func.avg(PostAnalytics.engagement_rate))
            .join(PublishedPost)
            .where(func.date(PublishedPost.published_at) >= cutoff_date)
        )
        avg_engagement = avg_engagement_result.scalar() or 0.0

        # Get subscriber growth over period
        snapshots_result = await db_session.execute(
            select(ChannelSnapshot)
            .where(ChannelSnapshot.snapshot_date >= cutoff_date)
            .order_by(ChannelSnapshot.snapshot_date)
        )
        snapshots = snapshots_result.scalars().all()
        subscriber_growth = sum(s.subscriber_growth for s in snapshots)

        return {
            "period_days": days,
            "current_subscribers": latest_snapshot.subscriber_count if latest_snapshot else 0,
            "subscriber_growth": subscriber_growth,
            "total_posts": total_posts,
            "total_views": total_views,
            "avg_engagement_rate": round(avg_engagement, 2),
        }
