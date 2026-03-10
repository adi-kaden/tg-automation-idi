"""
Analytics Collector Service.

Collects engagement metrics from Telegram for published posts and channel stats.

Uses Telethon (MTProto API) for per-message analytics (views, reactions, forwards)
and python-telegram-bot (Bot API) for channel-level stats (subscriber count).
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional

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
    Collect analytics from Telegram using Telethon (MTProto) for message stats
    and Bot API for channel-level stats.
    """

    def __init__(self):
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not configured")
        if not settings.telegram_channel_id:
            raise ValueError("TELEGRAM_CHANNEL_ID not configured")

        self.bot = Bot(token=settings.telegram_bot_token)
        self.channel_id = settings.telegram_channel_id
        self._telethon_client = None
        self._channel_entity = None

    async def connect(self):
        """Initialize and connect the Telethon client."""
        if not all([settings.telegram_api_id, settings.telegram_api_hash, settings.telegram_session_string]):
            logger.warning("Telethon not configured (missing TELEGRAM_API_ID, TELEGRAM_API_HASH, or TELEGRAM_SESSION_STRING)")
            return

        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession

            self._telethon_client = TelegramClient(
                StringSession(settings.telegram_session_string),
                int(settings.telegram_api_id),
                settings.telegram_api_hash,
            )
            await self._telethon_client.connect()

            if not await self._telethon_client.is_user_authorized():
                logger.error("Telethon session is not authorized. Run generate_telethon_session.py again.")
                self._telethon_client = None
                return

            # Cache the channel entity
            self._channel_entity = await self._telethon_client.get_entity(self.channel_id)
            logger.info(f"Telethon connected to channel: {self._channel_entity.title}")

        except Exception as e:
            logger.error(f"Failed to connect Telethon: {e}")
            self._telethon_client = None

    async def disconnect(self):
        """Disconnect the Telethon client."""
        if self._telethon_client:
            try:
                await self._telethon_client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting Telethon: {e}")
            finally:
                self._telethon_client = None
                self._channel_entity = None

    @property
    def has_telethon(self) -> bool:
        """Check if Telethon client is connected and ready."""
        return self._telethon_client is not None and self._channel_entity is not None

    async def get_channel_stats(self) -> Optional[ChannelStats]:
        """
        Get current channel statistics using Bot API.
        """
        try:
            chat = await self.bot.get_chat(self.channel_id)

            subscriber_count = getattr(chat, "member_count", None)
            if subscriber_count is None:
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
        Get statistics for a specific post using Telethon.
        """
        if not self.has_telethon:
            logger.debug(f"Telethon not available, returning zeros for message {message_id}")
            return PostStats(message_id=message_id)

        try:
            messages = await self._telethon_client.get_messages(
                self._channel_entity, ids=message_id
            )
            msg = messages if not isinstance(messages, list) else (messages[0] if messages else None)

            if not msg:
                logger.warning(f"Message {message_id} not found in channel")
                return PostStats(message_id=message_id)

            return self._parse_message_stats(msg)

        except Exception as e:
            logger.error(f"Failed to get post stats for message {message_id}: {e}")
            return PostStats(message_id=message_id)

    async def get_batch_post_stats(self, message_ids: list[int]) -> dict[int, PostStats]:
        """
        Get statistics for multiple posts in a single Telethon call.

        Returns:
            Dict mapping message_id to PostStats
        """
        if not self.has_telethon or not message_ids:
            return {mid: PostStats(message_id=mid) for mid in message_ids}

        try:
            from telethon.errors import FloodWaitError

            messages = await self._telethon_client.get_messages(
                self._channel_entity, ids=message_ids
            )

            results = {}
            for msg in messages:
                if msg is None:
                    continue
                results[msg.id] = self._parse_message_stats(msg)

            # Fill in any missing message IDs with empty stats
            for mid in message_ids:
                if mid not in results:
                    results[mid] = PostStats(message_id=mid)

            return results

        except Exception as e:
            # Import here to handle case where telethon isn't installed
            try:
                from telethon.errors import FloodWaitError
                if isinstance(e, FloodWaitError):
                    logger.warning(f"FloodWait: need to wait {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    # Retry once
                    return await self.get_batch_post_stats(message_ids)
            except ImportError:
                pass

            logger.error(f"Failed to get batch post stats: {e}")
            return {mid: PostStats(message_id=mid) for mid in message_ids}

    def _parse_message_stats(self, msg) -> PostStats:
        """Parse a Telethon Message object into PostStats."""
        views = msg.views or 0
        forwards = msg.forwards or 0
        replies = 0
        if msg.replies:
            replies = msg.replies.replies or 0

        reactions = {}
        if msg.reactions and msg.reactions.results:
            for r in msg.reactions.results:
                emoji = getattr(r.reaction, 'emoticon', None) or str(r.reaction)
                reactions[emoji] = r.count

        return PostStats(
            message_id=msg.id,
            views=views,
            forwards=forwards,
            replies=replies,
            reactions=reactions,
        )

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
        """
        if views == 0:
            return 0.0

        engagement = forwards + replies + reactions_total
        return round((engagement / views) * 100, 2)

    async def collect_all_post_analytics(
        self,
        db_session,
        days_back: int = 7,
    ) -> dict:
        """
        Collect analytics for recent published posts using batch Telethon calls.

        Args:
            db_session: Database session
            days_back: How far back to look for posts (default 7 days)
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.published_post import PublishedPost
        from app.models.post_analytics import PostAnalytics

        cutoff = datetime.utcnow() - timedelta(days=days_back)

        # Get recent published posts
        result = await db_session.execute(
            select(PublishedPost)
            .options(selectinload(PublishedPost.analytics))
            .where(PublishedPost.published_at >= cutoff)
        )
        posts = result.scalars().all()

        # Collect message IDs for batch fetch
        posts_with_msg_id = [p for p in posts if p.telegram_message_id]
        message_ids = [p.telegram_message_id for p in posts_with_msg_id]

        if not message_ids:
            logger.info("No published posts with telegram_message_id found")
            return {"posts_processed": 0, "updated": 0, "created": 0, "errors": 0}

        # Batch fetch all stats in one API call
        all_stats = await self.get_batch_post_stats(message_ids)

        updated = 0
        created = 0
        errors = 0
        now = datetime.utcnow()

        for post in posts_with_msg_id:
            try:
                stats = all_stats.get(post.telegram_message_id)
                if not stats:
                    errors += 1
                    continue

                reactions_total = sum(stats.reactions.values()) if stats.reactions else 0
                engagement_rate = self.calculate_engagement_rate(
                    views=stats.views,
                    forwards=stats.forwards,
                    replies=stats.replies,
                    reactions_total=reactions_total,
                )

                if post.analytics:
                    analytics = post.analytics
                    prev_views = analytics.views

                    analytics.views = stats.views
                    analytics.forwards = stats.forwards
                    analytics.replies = stats.replies
                    analytics.reactions = json.dumps(stats.reactions) if stats.reactions else None
                    analytics.engagement_rate = engagement_rate
                    analytics.last_fetched_at = now

                    # Calculate view growth
                    if prev_views > 0 and stats.views > 0:
                        analytics.view_growth_1h = round(
                            ((stats.views - prev_views) / prev_views) * 100, 2
                        )

                    # Calculate 24h growth from snapshots
                    snapshots = []
                    if analytics.hourly_snapshots:
                        try:
                            snapshots = json.loads(analytics.hourly_snapshots)
                        except json.JSONDecodeError:
                            snapshots = []

                    # Find snapshot closest to 24h ago for growth calculation
                    target_time = now - timedelta(hours=24)
                    if snapshots:
                        closest_snapshot = None
                        closest_diff = float('inf')
                        for snap in snapshots:
                            try:
                                snap_time = datetime.fromisoformat(snap["timestamp"])
                                diff = abs((snap_time - target_time).total_seconds())
                                if diff < closest_diff:
                                    closest_diff = diff
                                    closest_snapshot = snap
                            except (KeyError, ValueError):
                                continue

                        if closest_snapshot and closest_snapshot.get("views", 0) > 0:
                            old_views = closest_snapshot["views"]
                            analytics.view_growth_24h = round(
                                ((stats.views - old_views) / old_views) * 100, 2
                            )

                    # Append new snapshot
                    snapshots.append({
                        "timestamp": now.isoformat(),
                        "views": stats.views,
                        "forwards": stats.forwards,
                        "reactions": reactions_total,
                    })

                    # Keep last 2016 snapshots (7 days at 5-min intervals)
                    analytics.hourly_snapshots = json.dumps(snapshots[-2016:])
                    updated += 1
                else:
                    analytics = PostAnalytics(
                        post_id=post.id,
                        views=stats.views,
                        forwards=stats.forwards,
                        replies=stats.replies,
                        reactions=json.dumps(stats.reactions) if stats.reactions else None,
                        engagement_rate=engagement_rate,
                        hourly_snapshots=json.dumps([{
                            "timestamp": now.isoformat(),
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

        logger.info(
            f"Analytics collection: {len(posts_with_msg_id)} posts, "
            f"{updated} updated, {created} created, {errors} errors"
        )

        return {
            "posts_processed": len(posts_with_msg_id),
            "updated": updated,
            "created": created,
            "errors": errors,
        }

    async def create_daily_snapshot(self, db_session, snapshot_date: date = None) -> dict:
        """
        Create a daily channel snapshot.
        """
        from sqlalchemy import select, func
        from app.models.channel_snapshot import ChannelSnapshot
        from app.models.published_post import PublishedPost
        from app.models.post_analytics import PostAnalytics

        if not snapshot_date:
            snapshot_date = date.today()

        existing = await db_session.execute(
            select(ChannelSnapshot).where(ChannelSnapshot.snapshot_date == snapshot_date)
        )
        if existing.scalar_one_or_none():
            logger.info(f"Snapshot for {snapshot_date} already exists")
            return {"status": "exists", "date": str(snapshot_date)}

        channel_stats = await self.get_channel_stats()
        subscriber_count = channel_stats.subscriber_count if channel_stats else 0

        prev_date = snapshot_date - timedelta(days=1)
        prev_result = await db_session.execute(
            select(ChannelSnapshot).where(ChannelSnapshot.snapshot_date == prev_date)
        )
        prev_snapshot = prev_result.scalar_one_or_none()
        subscriber_growth = 0
        if prev_snapshot:
            subscriber_growth = subscriber_count - prev_snapshot.subscriber_count

        posts_result = await db_session.execute(
            select(func.count(PublishedPost.id))
            .where(func.date(PublishedPost.published_at) == snapshot_date)
        )
        posts_published = posts_result.scalar() or 0

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

        top_post_result = await db_session.execute(
            select(PostAnalytics.post_id)
            .join(PublishedPost)
            .where(func.date(PublishedPost.published_at) == snapshot_date)
            .order_by(PostAnalytics.views.desc())
            .limit(1)
        )
        top_post_row = top_post_result.one_or_none()
        top_post_id = top_post_row[0] if top_post_row else None

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
        """
        from sqlalchemy import select, func
        from app.models.channel_snapshot import ChannelSnapshot
        from app.models.published_post import PublishedPost
        from app.models.post_analytics import PostAnalytics

        cutoff_date = date.today() - timedelta(days=days)

        latest_snapshot_result = await db_session.execute(
            select(ChannelSnapshot)
            .order_by(ChannelSnapshot.snapshot_date.desc())
            .limit(1)
        )
        latest_snapshot = latest_snapshot_result.scalar_one_or_none()

        posts_count_result = await db_session.execute(
            select(func.count(PublishedPost.id))
            .where(func.date(PublishedPost.published_at) >= cutoff_date)
        )
        total_posts = posts_count_result.scalar() or 0

        views_result = await db_session.execute(
            select(func.sum(PostAnalytics.views))
            .join(PublishedPost)
            .where(func.date(PublishedPost.published_at) >= cutoff_date)
        )
        total_views = views_result.scalar() or 0

        avg_engagement_result = await db_session.execute(
            select(func.avg(PostAnalytics.engagement_rate))
            .join(PublishedPost)
            .where(func.date(PublishedPost.published_at) >= cutoff_date)
        )
        avg_engagement = avg_engagement_result.scalar() or 0.0

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
