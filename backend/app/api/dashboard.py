from datetime import datetime, timedelta, date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.dependencies import DBSession, CurrentUser
from app.models.content_slot import ContentSlot
from app.models.published_post import PublishedPost
from app.models.post_analytics import PostAnalytics
from app.models.channel_snapshot import ChannelSnapshot
from app.utils.timezone import now_dubai, to_dubai, DUBAI_TZ
from app.services.analytics_collector import AnalyticsCollector

router = APIRouter()


class DashboardStats(BaseModel):
    """Dashboard statistics."""
    posts_today: int
    posts_published: int
    pending_review: int
    subscribers: int
    subscriber_change: int
    avg_engagement_rate: float


class SlotSummary(BaseModel):
    """Summary of a content slot for dashboard."""
    id: UUID
    scheduled_time: str
    content_type: str
    status: str
    has_options: bool
    selected_option_label: Optional[str]
    minutes_until_deadline: Optional[int]


class TodaySchedule(BaseModel):
    """Today's posting schedule."""
    date: str
    slots: List[SlotSummary]


class PendingAction(BaseModel):
    """An action that needs SMM attention."""
    id: UUID
    type: str
    title: str
    description: str
    deadline: Optional[datetime]
    urgency: str  # low, medium, high, critical


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Get overview statistics for the dashboard.
    """
    today = now_dubai().date()

    # Count today's slots
    slots_result = await db.execute(
        select(func.count(ContentSlot.id))
        .where(ContentSlot.scheduled_date == today)
    )
    posts_today = slots_result.scalar_one()

    # Count published today
    published_result = await db.execute(
        select(func.count(ContentSlot.id))
        .where(
            and_(
                ContentSlot.scheduled_date == today,
                ContentSlot.status == "published"
            )
        )
    )
    posts_published = published_result.scalar_one()

    # Count pending review
    pending_result = await db.execute(
        select(func.count(ContentSlot.id))
        .where(
            and_(
                ContentSlot.scheduled_date == today,
                ContentSlot.status == "options_ready",
                ContentSlot.selected_option_id.is_(None)
            )
        )
    )
    pending_review = pending_result.scalar_one()

    # Get latest channel snapshot
    snapshot_result = await db.execute(
        select(ChannelSnapshot)
        .order_by(ChannelSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snapshot = snapshot_result.scalar_one_or_none()

    subscribers = snapshot.subscriber_count if snapshot else 0
    subscriber_change = snapshot.subscriber_growth if snapshot else 0
    avg_engagement = snapshot.avg_engagement_rate if snapshot else 0.0

    return DashboardStats(
        posts_today=posts_today or 5,  # Default 5 slots per day
        posts_published=posts_published,
        pending_review=pending_review,
        subscribers=subscribers,
        subscriber_change=subscriber_change,
        avg_engagement_rate=avg_engagement,
    )


@router.get("/today", response_model=TodaySchedule)
async def get_today_schedule(
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Get today's posting schedule with slot statuses.
    """
    today = now_dubai().date()
    now = now_dubai()

    # Get today's slots with options eagerly loaded
    result = await db.execute(
        select(ContentSlot)
        .options(selectinload(ContentSlot.options))
        .where(ContentSlot.scheduled_date == today)
        .order_by(ContentSlot.slot_number)
    )
    slots = result.scalars().all()

    slot_summaries = []
    for slot in slots:
        # Calculate minutes until deadline
        deadline_dubai = to_dubai(slot.approval_deadline)
        minutes_until = None
        if deadline_dubai > now:
            delta = deadline_dubai - now
            minutes_until = int(delta.total_seconds() / 60)

        # Check if has options
        has_options = len(slot.options) > 0 if slot.options else False

        # Get selected option label
        selected_label = None
        if slot.selected_option_id:
            for opt in slot.options:
                if opt.id == slot.selected_option_id:
                    selected_label = opt.option_label
                    break

        slot_summaries.append(SlotSummary(
            id=slot.id,
            scheduled_time=slot.scheduled_time,
            content_type=slot.content_type,
            status=slot.status,
            has_options=has_options,
            selected_option_label=selected_label,
            minutes_until_deadline=minutes_until,
        ))

    return TodaySchedule(
        date=today.isoformat(),
        slots=slot_summaries,
    )


@router.get("/pending", response_model=List[PendingAction])
async def get_pending_actions(
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Get items needing SMM attention.
    """
    today = now_dubai().date()
    now = now_dubai()

    # Get slots needing selection
    result = await db.execute(
        select(ContentSlot)
        .where(
            and_(
                ContentSlot.scheduled_date == today,
                ContentSlot.status == "options_ready",
                ContentSlot.selected_option_id.is_(None)
            )
        )
        .order_by(ContentSlot.scheduled_at)
    )
    pending_slots = result.scalars().all()

    actions = []
    for slot in pending_slots:
        deadline_dubai = to_dubai(slot.approval_deadline)
        minutes_until = int((deadline_dubai - now).total_seconds() / 60)

        # Determine urgency
        if minutes_until <= 10:
            urgency = "critical"
        elif minutes_until <= 30:
            urgency = "high"
        elif minutes_until <= 60:
            urgency = "medium"
        else:
            urgency = "low"

        content_type_label = "Real Estate" if slot.content_type == "real_estate" else "Dubai Trending"

        actions.append(PendingAction(
            id=slot.id,
            type="slot_selection",
            title=f"{slot.scheduled_time} - {content_type_label}",
            description=f"Select post option for the {slot.scheduled_time} slot",
            deadline=slot.approval_deadline,
            urgency=urgency,
        ))

    return actions


# ==================== Analytics Endpoints ====================

class AnalyticsSummary(BaseModel):
    """Analytics summary for a period."""
    period_days: int
    current_subscribers: int
    subscriber_growth: int
    total_posts: int
    total_views: int
    avg_engagement_rate: float


class TopPost(BaseModel):
    """Top performing post."""
    id: UUID
    title: str
    published_at: datetime
    views: int
    engagement_rate: float
    content_type: str


class ChannelGrowth(BaseModel):
    """Channel growth data point."""
    date: str
    subscribers: int
    growth: int
    posts_published: int
    avg_views: float


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    db: DBSession,
    current_user: CurrentUser,
    days: int = Query(default=7, ge=1, le=90),
):
    """
    Get analytics summary for the specified period.
    """
    try:
        collector = AnalyticsCollector()
        result = await collector.get_analytics_summary(db, days=days)
        return AnalyticsSummary(**result)
    except ValueError:
        # Telegram not configured - return empty stats
        return AnalyticsSummary(
            period_days=days,
            current_subscribers=0,
            subscriber_growth=0,
            total_posts=0,
            total_views=0,
            avg_engagement_rate=0.0,
        )


@router.get("/analytics/top-posts", response_model=List[TopPost])
async def get_top_posts(
    db: DBSession,
    current_user: CurrentUser,
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Get top performing posts by views.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(PublishedPost, PostAnalytics)
        .join(PostAnalytics, PostAnalytics.post_id == PublishedPost.id)
        .where(PublishedPost.published_at >= cutoff)
        .order_by(PostAnalytics.views.desc())
        .limit(limit)
    )
    rows = result.all()

    return [
        TopPost(
            id=post.id,
            title=post.posted_title,
            published_at=post.published_at,
            views=analytics.views,
            engagement_rate=analytics.engagement_rate,
            content_type=post.posted_language,  # Using language as proxy for now
        )
        for post, analytics in rows
    ]


@router.get("/analytics/growth", response_model=List[ChannelGrowth])
async def get_channel_growth(
    db: DBSession,
    current_user: CurrentUser,
    days: int = Query(default=30, ge=1, le=90),
):
    """
    Get channel growth data for charting.
    """
    cutoff = date.today() - timedelta(days=days)

    result = await db.execute(
        select(ChannelSnapshot)
        .where(ChannelSnapshot.snapshot_date >= cutoff)
        .order_by(ChannelSnapshot.snapshot_date)
    )
    snapshots = result.scalars().all()

    return [
        ChannelGrowth(
            date=snapshot.snapshot_date.isoformat(),
            subscribers=snapshot.subscriber_count,
            growth=snapshot.subscriber_growth,
            posts_published=snapshot.posts_published,
            avg_views=snapshot.avg_views,
        )
        for snapshot in snapshots
    ]


@router.post("/analytics/collect")
async def trigger_analytics_collection(
    db: DBSession,
    current_user: CurrentUser,
    hours_back: int = Query(default=48, ge=1, le=168),
):
    """
    Manually trigger analytics collection.
    """
    from app.tasks.analytics_tasks import collect_post_analytics

    task = collect_post_analytics.delay(hours_back=hours_back)

    return {
        "status": "queued",
        "task_id": task.id,
        "hours_back": hours_back,
    }


@router.post("/analytics/snapshot")
async def create_snapshot(
    db: DBSession,
    current_user: CurrentUser,
    snapshot_date: Optional[str] = Query(None),
):
    """
    Manually create a channel snapshot.
    """
    from app.tasks.analytics_tasks import create_daily_channel_snapshot

    task = create_daily_channel_snapshot.delay(snapshot_date_str=snapshot_date)

    return {
        "status": "queued",
        "task_id": task.id,
        "date": snapshot_date or date.today().isoformat(),
    }
