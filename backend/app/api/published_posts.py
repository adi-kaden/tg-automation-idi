"""
API endpoints for published posts with real analytics.
"""
import base64
import json
import math
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException, Response
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import selectinload, joinedload

from app.dependencies import DBSession, CurrentUser
from app.models.published_post import PublishedPost
from app.models.post_analytics import PostAnalytics
from app.models.content_slot import ContentSlot
from app.models.post_option import PostOption
from app.schemas.content import (
    PublishedPostDetailResponse,
    PublishedPostListResponse,
    PostAnalyticsResponse,
)

router = APIRouter()

CHANNEL_USERNAME = "idigovnews"


def _build_post_response(post: PublishedPost, content_type: Optional[str] = None) -> PublishedPostDetailResponse:
    """Build a PublishedPostDetailResponse from a PublishedPost model instance."""
    # Build telegram link
    telegram_link = None
    if post.telegram_message_id:
        telegram_link = f"https://t.me/{CHANNEL_USERNAME}/{post.telegram_message_id}"

    # Build image URL
    image_url_served = f"/api/published-posts/{post.id}/image"

    # Build analytics response
    analytics_resp = None
    if post.analytics:
        a = post.analytics
        reactions = None
        if a.reactions:
            try:
                reactions = json.loads(a.reactions) if isinstance(a.reactions, str) else a.reactions
            except (json.JSONDecodeError, TypeError):
                reactions = None

        analytics_resp = PostAnalyticsResponse(
            id=a.id,
            post_id=a.post_id,
            views=a.views,
            forwards=a.forwards,
            replies=a.replies,
            reactions=reactions,
            engagement_rate=a.engagement_rate,
            view_growth_1h=a.view_growth_1h,
            view_growth_24h=a.view_growth_24h,
            last_fetched_at=a.last_fetched_at,
        )

    return PublishedPostDetailResponse(
        id=post.id,
        slot_id=post.slot_id,
        option_id=post.option_id,
        posted_title=post.posted_title,
        posted_body=post.posted_body,
        posted_language=post.posted_language,
        posted_image_url=post.posted_image_url,
        telegram_message_id=post.telegram_message_id,
        telegram_channel_id=post.telegram_channel_id,
        selected_by=post.selected_by,
        selected_by_user_id=post.selected_by_user_id,
        published_at=post.published_at,
        analytics=analytics_resp,
        content_type=content_type,
        telegram_link=telegram_link,
        image_url_served=image_url_served,
    )


@router.get("", response_model=PublishedPostListResponse)
async def list_published_posts(
    db: DBSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    content_type: Optional[str] = Query(default=None),
    language: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    sort_by: str = Query(default="published_at"),
    sort_order: str = Query(default="desc"),
):
    """
    List published posts with pagination, sorting, and filtering.
    """
    # Base query
    query = (
        select(PublishedPost, ContentSlot.content_type)
        .outerjoin(PostAnalytics, PostAnalytics.post_id == PublishedPost.id)
        .join(ContentSlot, ContentSlot.id == PublishedPost.slot_id)
        .options(selectinload(PublishedPost.analytics))
    )

    # Apply filters
    if content_type:
        query = query.where(ContentSlot.content_type == content_type)
    if language:
        query = query.where(PublishedPost.posted_language == language)
    if date_from:
        query = query.where(func.date(PublishedPost.published_at) >= date_from)
    if date_to:
        query = query.where(func.date(PublishedPost.published_at) <= date_to)

    # Count total
    count_query = select(func.count(PublishedPost.id)).join(
        ContentSlot, ContentSlot.id == PublishedPost.slot_id
    )
    if content_type:
        count_query = count_query.where(ContentSlot.content_type == content_type)
    if language:
        count_query = count_query.where(PublishedPost.posted_language == language)
    if date_from:
        count_query = count_query.where(func.date(PublishedPost.published_at) >= date_from)
    if date_to:
        count_query = count_query.where(func.date(PublishedPost.published_at) <= date_to)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column_map = {
        "published_at": PublishedPost.published_at,
        "views": PostAnalytics.views,
        "engagement_rate": PostAnalytics.engagement_rate,
        "forwards": PostAnalytics.forwards,
    }
    sort_col = sort_column_map.get(sort_by, PublishedPost.published_at)
    order_func = desc if sort_order == "desc" else asc

    # Handle NULL analytics when sorting by analytics columns
    if sort_by in ("views", "engagement_rate", "forwards"):
        if sort_order == "desc":
            query = query.order_by(sort_col.desc().nulls_last())
        else:
            query = query.order_by(sort_col.asc().nulls_last())
    else:
        query = query.order_by(order_func(sort_col))

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    rows = result.all()

    items = [
        _build_post_response(post, content_type=ct)
        for post, ct in rows
    ]

    pages = math.ceil(total / per_page) if total > 0 else 1

    return PublishedPostListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{post_id}", response_model=PublishedPostDetailResponse)
async def get_published_post(
    post_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Get a single published post with full analytics.
    """
    result = await db.execute(
        select(PublishedPost, ContentSlot.content_type)
        .join(ContentSlot, ContentSlot.id == PublishedPost.slot_id)
        .options(selectinload(PublishedPost.analytics))
        .where(PublishedPost.id == post_id)
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Published post not found")

    post, content_type = row
    return _build_post_response(post, content_type=content_type)


@router.get("/{post_id}/image")
async def get_post_image(
    post_id: UUID,
    db: DBSession,
):
    """
    Serve the image for a published post.
    Unauthenticated — images are already public on Telegram.
    """
    # Get the published post to find the option
    result = await db.execute(
        select(PublishedPost).where(PublishedPost.id == post_id)
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Get the post option which has the image data
    option_result = await db.execute(
        select(PostOption).where(PostOption.id == post.option_id)
    )
    option = option_result.scalar_one_or_none()

    if not option:
        raise HTTPException(status_code=404, detail="Post option not found")

    # Try image_data (base64) first
    if option.image_data:
        try:
            image_bytes = base64.b64decode(option.image_data)
            return Response(
                content=image_bytes,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except Exception:
            pass

    # Try image_url redirect
    if option.image_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=option.image_url)

    raise HTTPException(status_code=404, detail="No image available for this post")
