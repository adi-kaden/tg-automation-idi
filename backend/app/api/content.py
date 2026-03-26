"""
REST API endpoints for content slots and post options.
"""
import json
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.content_slot import ContentSlot
from app.models.post_option import PostOption
from app.models.published_post import PublishedPost
from app.models.user import User
from app.schemas.content import (
    ContentSlotResponse,
    ContentSlotDetail,
    ContentSlotUpdate,
    PostOptionResponse,
    PostOptionUpdate,
    SlotSelectionRequest,
    SlotSelectionResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    DailySlotsRequest,
    DailySlotsResponse,
    ContentQueueResponse,
    PublishRequest,
    PublishResponse,
)
from app.services.content.slot_manager import SlotManager, DUBAI_TZ
from app.services.telegram_publisher import TelegramPublisher, PostContent
from app.services.notification_service import SMMNotificationService
from app.tasks.content_tasks import (
    create_daily_slots_task,
    generate_content_for_slot,
    auto_select_for_slot,
)
from app.dependencies import get_current_user

router = APIRouter()


# ==================== Content Slots ====================

@router.get("/slots", response_model=list[ContentSlotResponse])
async def list_slots(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List content slots with optional filters.
    """
    query = select(ContentSlot).order_by(ContentSlot.scheduled_at.desc())

    if date_from:
        query = query.where(ContentSlot.scheduled_date >= date_from)
    if date_to:
        query = query.where(ContentSlot.scheduled_date <= date_to)
    if status:
        query = query.where(ContentSlot.status == status)
    if content_type:
        query = query.where(ContentSlot.content_type == content_type)

    result = await db.execute(query.limit(100))
    slots = result.scalars().all()

    return slots


@router.get("/slots/{slot_id}", response_model=ContentSlotDetail)
async def get_slot(
    slot_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a content slot including its options.
    """
    result = await db.execute(
        select(ContentSlot)
        .options(selectinload(ContentSlot.options))
        .where(ContentSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    return slot


@router.post("/slots/create-daily", response_model=DailySlotsResponse)
async def create_daily_slots(
    request: DailySlotsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create all 5 content slots for a given date.
    """
    manager = SlotManager(db)
    slots = await manager.create_daily_slots(request.target_date)

    return DailySlotsResponse(
        date=request.target_date,
        slots_created=len(slots),
        slots=slots,
    )


@router.post("/slots/{slot_id}/generate", response_model=ContentGenerationResponse)
async def trigger_content_generation(
    slot_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger AI content generation for a slot.
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"Regenerate requested for slot {slot_id}")

    # Verify slot exists
    result = await db.execute(
        select(ContentSlot).where(ContentSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot:
        logger.error(f"Slot {slot_id} not found")
        raise HTTPException(status_code=404, detail="Slot not found")

    logger.info(f"Slot {slot_id} current status: {slot.status}")

    if slot.status == "published":
        raise HTTPException(
            status_code=400,
            detail="Cannot regenerate a published slot"
        )

    # Allow regeneration for pending, failed, options_ready, and approved slots
    # Reset slot status and clear existing selection
    if slot.status in ["options_ready", "approved"]:
        slot.selected_option_id = None
        slot.selected_by = None
        slot.selected_by_user_id = None
        logger.info(f"Cleared selection for slot {slot_id}")

    # Set status to "generating" NOW so the frontend polling works correctly.
    # Without this, the first poll sees the old status and stops immediately.
    slot.status = "generating"
    await db.commit()
    logger.info(f"Set slot {slot_id} status to generating")

    # Trigger async task
    try:
        task = generate_content_for_slot.delay(str(slot_id))
        logger.info(f"Celery task queued: {task.id} for slot {slot_id}")
    except Exception as e:
        logger.error(f"Failed to queue Celery task for slot {slot_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue generation task: {str(e)}")

    return ContentGenerationResponse(
        slot_id=slot_id,
        task_id=task.id,
        status="queued",
    )


@router.post("/slots/{slot_id}/select", response_model=SlotSelectionResponse)
async def select_option(
    slot_id: UUID,
    request: SlotSelectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Select a post option for publishing (SMM manual selection).
    """
    # Get slot with options
    result = await db.execute(
        select(ContentSlot)
        .options(selectinload(ContentSlot.options))
        .where(ContentSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    if slot.status not in ["options_ready", "approved"]:
        raise HTTPException(
            status_code=400,
            detail=f"Slot is in '{slot.status}' state, cannot select"
        )

    # Verify option belongs to this slot
    option = next(
        (opt for opt in slot.options if opt.id == request.option_id),
        None
    )

    if not option:
        raise HTTPException(
            status_code=400,
            detail="Option does not belong to this slot"
        )

    # Update selection
    manager = SlotManager(db)
    await manager.update_slot_status(
        slot_id=slot_id,
        status="approved",
        selected_option_id=request.option_id,
        selected_by="human",
        selected_by_user_id=current_user.id,
    )

    return SlotSelectionResponse(
        slot_id=slot_id,
        selected_option_id=request.option_id,
        selected_by="human",
        status="approved",
    )


@router.post("/slots/{slot_id}/auto-select", response_model=ContentGenerationResponse)
async def trigger_auto_select(
    slot_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger AI auto-selection for a slot.
    """
    result = await db.execute(
        select(ContentSlot).where(ContentSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    if slot.status != "options_ready":
        raise HTTPException(
            status_code=400,
            detail=f"Slot must be in 'options_ready' state, currently '{slot.status}'"
        )

    task = auto_select_for_slot.delay(str(slot_id))

    return ContentGenerationResponse(
        slot_id=slot_id,
        task_id=task.id,
        status="queued",
    )


@router.post("/slots/{slot_id}/publish", response_model=PublishResponse)
async def publish_slot(
    slot_id: UUID,
    request: PublishRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Publish an approved slot to Telegram.

    The slot must be in 'approved' status with a selected option.
    """
    # Get slot with selected option
    result = await db.execute(
        select(ContentSlot)
        .options(selectinload(ContentSlot.options))
        .where(ContentSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    if slot.status == "published":
        raise HTTPException(
            status_code=400,
            detail="Slot has already been published"
        )

    if slot.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Slot must be in 'approved' status, currently '{slot.status}'"
        )

    if not slot.selected_option_id:
        raise HTTPException(
            status_code=400,
            detail="No option selected for this slot"
        )

    # Get the selected option
    option = next(
        (opt for opt in slot.options if opt.id == slot.selected_option_id),
        None
    )

    if not option:
        raise HTTPException(
            status_code=400,
            detail="Selected option not found"
        )

    # Initialize publisher
    try:
        publisher = TelegramPublisher()
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Telegram not configured: {e}"
        )

    # Parse hashtags from JSON string
    hashtags = []
    if option.hashtags:
        try:
            hashtags = json.loads(option.hashtags)
        except json.JSONDecodeError:
            hashtags = []

    # Parse album images if present
    album_images = None
    if option.album_images_data:
        try:
            album_images = json.loads(option.album_images_data)
        except json.JSONDecodeError:
            album_images = None

    # Create post content (Russian only)
    content = PostContent(
        title_ru=option.title_ru,
        body_ru=option.body_ru,
        hashtags=hashtags,
        image_url=option.image_url,
        image_local_path=option.image_local_path,
        image_data=option.image_data,  # Base64 encoded image
        album_images_data=album_images,
    )

    # Publish to Telegram (album or single post)
    if album_images and len(album_images) > 0:
        publish_result = await publisher.publish_album(content)
    else:
        publish_result = await publisher.publish_post(content)

    if not publish_result.success:
        return PublishResponse(
            slot_id=slot_id,
            success=False,
            error=publish_result.error,
            channel_id=publish_result.channel_id,
        )

    # Create PublishedPost record (Russian only)
    published_post = PublishedPost(
        slot_id=slot_id,
        option_id=option.id,
        posted_title=option.title_ru,
        posted_body=option.body_ru,
        posted_language="ru",
        posted_image_url=option.image_url,
        telegram_message_id=publish_result.message_id_ru,
        telegram_channel_id=publish_result.channel_id,
        selected_by=slot.selected_by or "human",
        selected_by_user_id=slot.selected_by_user_id,
    )
    db.add(published_post)

    # Update slot status
    slot.status = "published"
    slot.published_post_id = published_post.id

    await db.commit()

    return PublishResponse(
        slot_id=slot_id,
        success=True,
        message_id_en=publish_result.message_id_en,
        message_id_ru=publish_result.message_id_ru,
        published_post_id=published_post.id,
        channel_id=publish_result.channel_id,
    )


@router.patch("/slots/{slot_id}", response_model=ContentSlotResponse)
async def update_slot(
    slot_id: UUID,
    update: ContentSlotUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a content slot (e.g., toggle album_mode).
    """
    result = await db.execute(
        select(ContentSlot).where(ContentSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(slot, field, value)

    await db.commit()
    await db.refresh(slot)

    return slot


@router.post("/slots/{slot_id}/reset")
async def reset_slot(
    slot_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reset a slot back to pending status.
    Useful for re-generating content or fixing incorrect status.
    """
    result = await db.execute(
        select(ContentSlot).where(ContentSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    old_status = slot.status
    slot.status = "pending"
    slot.selected_option_id = None
    slot.selected_by = None
    slot.selected_by_user_id = None
    slot.published_post_id = None

    await db.commit()

    return {
        "slot_id": str(slot_id),
        "old_status": old_status,
        "new_status": "pending",
        "message": "Slot reset successfully"
    }


@router.post("/slots/cleanup-old")
async def cleanup_old_slots(
    keep_date: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete slots older than the specified date (or older than today if not specified).
    This helps clean up duplicate slots from testing.
    """
    from datetime import date as date_type
    from sqlalchemy import func, update
    from sqlalchemy import delete as sql_delete
    from app.models.post_option import PostOption
    from app.models.published_post import PublishedPost
    from app.models.scraped_article import ScrapedArticle

    if keep_date:
        cutoff_date = date_type.fromisoformat(keep_date)
    else:
        from zoneinfo import ZoneInfo
        cutoff_date = datetime.now(ZoneInfo("Asia/Dubai")).date()

    # Get old slot IDs
    result = await db.execute(
        select(ContentSlot.id).where(
            func.date(ContentSlot.scheduled_at) < cutoff_date
        )
    )
    old_slot_ids = [row[0] for row in result.fetchall()]

    if not old_slot_ids:
        return {
            "deleted_count": 0,
            "cutoff_date": str(cutoff_date),
            "message": "No old slots to delete"
        }

    # Get option IDs for these slots
    result = await db.execute(
        select(PostOption.id).where(PostOption.slot_id.in_(old_slot_ids))
    )
    old_option_ids = [row[0] for row in result.fetchall()]

    # Clear selected_option_id references in slots first
    await db.execute(
        update(ContentSlot)
        .where(ContentSlot.id.in_(old_slot_ids))
        .values(selected_option_id=None)
    )

    # Clear used_in_post_id references in articles
    if old_option_ids:
        await db.execute(
            update(ScrapedArticle)
            .where(ScrapedArticle.used_in_post_id.in_(old_option_ids))
            .values(used_in_post_id=None)
        )

    # Delete related published posts
    await db.execute(
        sql_delete(PublishedPost).where(PublishedPost.slot_id.in_(old_slot_ids))
    )

    # Delete related post options
    if old_option_ids:
        await db.execute(
            sql_delete(PostOption).where(PostOption.id.in_(old_option_ids))
        )

    # Now delete the slots
    result = await db.execute(
        sql_delete(ContentSlot).where(ContentSlot.id.in_(old_slot_ids))
    )
    deleted_count = result.rowcount

    await db.commit()

    return {
        "deleted_count": deleted_count,
        "cutoff_date": str(cutoff_date),
        "message": f"Deleted {deleted_count} old slots"
    }


# ==================== Post Options ====================

@router.get("/options/{option_id}", response_model=PostOptionResponse)
async def get_option(
    option_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a post option.
    """
    result = await db.execute(
        select(PostOption).where(PostOption.id == option_id)
    )
    option = result.scalar_one_or_none()

    if not option:
        raise HTTPException(status_code=404, detail="Option not found")

    return option


@router.patch("/options/{option_id}", response_model=PostOptionResponse)
async def update_option(
    option_id: UUID,
    update: PostOptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a post option (SMM editing content).
    """
    result = await db.execute(
        select(PostOption).where(PostOption.id == option_id)
    )
    option = result.scalar_one_or_none()

    if not option:
        raise HTTPException(status_code=404, detail="Option not found")

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(option, field, value)

    option.is_edited = True

    await db.commit()
    await db.refresh(option)

    return option


# ==================== Queue View ====================

@router.get("/queue", response_model=ContentQueueResponse)
async def get_content_queue(
    target_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the content queue for a specific date (defaults to today).

    This is the main view for the SMM dashboard.
    """
    if not target_date:
        target_date = datetime.now(DUBAI_TZ).date()

    manager = SlotManager(db)
    slots = await manager.get_slots_for_date(target_date)

    # Calculate stats
    stats = {
        "total_slots": len(slots),
        "pending": sum(1 for s in slots if s.status == "pending"),
        "generating": sum(1 for s in slots if s.status == "generating"),
        "options_ready": sum(1 for s in slots if s.status == "options_ready"),
        "approved": sum(1 for s in slots if s.status == "approved"),
        "published": sum(1 for s in slots if s.status == "published"),
        "failed": sum(1 for s in slots if s.status == "failed"),
    }

    return ContentQueueResponse(
        date=target_date,
        slots=slots,
        stats=stats,
    )


@router.get("/queue/upcoming")
async def get_upcoming_slots(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get slots scheduled in the next N hours.
    """
    now = datetime.now(DUBAI_TZ)
    from datetime import timedelta
    cutoff = now + timedelta(hours=hours)

    result = await db.execute(
        select(ContentSlot)
        .options(selectinload(ContentSlot.options))
        .where(
            and_(
                ContentSlot.scheduled_at >= now,
                ContentSlot.scheduled_at <= cutoff,
            )
        )
        .order_by(ContentSlot.scheduled_at)
    )
    slots = result.scalars().all()

    return {
        "from": now.isoformat(),
        "to": cutoff.isoformat(),
        "slots": slots,
    }


# ==================== Telegram ====================

@router.get("/telegram/test")
async def test_telegram_connection(
    current_user: User = Depends(get_current_user),
):
    """
    Test the Telegram bot connection and channel access.
    """
    try:
        publisher = TelegramPublisher()
        success, message = await publisher.test_connection()

        return {
            "success": success,
            "message": message,
        }
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
        }


@router.get("/telegram/channel-info")
async def get_telegram_channel_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get information about the configured Telegram channel.
    """
    try:
        publisher = TelegramPublisher()
        info = await publisher.get_channel_info()

        if info:
            return {
                "success": True,
                "channel": info,
            }
        else:
            return {
                "success": False,
                "message": "Could not retrieve channel info",
            }
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
        }


# ==================== Notifications ====================

@router.get("/notifications/test")
async def test_smm_notifications(
    current_user: User = Depends(get_current_user),
):
    """
    Test the SMM notification connection.

    Sends a test notification to the configured SMM chat.
    """
    try:
        service = SMMNotificationService()
        success, message = await service.test_connection()

        return {
            "success": success,
            "message": message,
        }
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
        }


@router.post("/notifications/send-test")
async def send_test_notification(
    notification_type: str = Query(
        default="options_ready",
        description="Type of notification to test"
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Send a test notification of the specified type.

    Available types: options_ready, auto_selected, publish_success, publish_failed
    """
    try:
        service = SMMNotificationService()

        if notification_type == "options_ready":
            result = await service.notify_options_ready(
                slot_id="test-slot-id",
                scheduled_time="08:00",
                content_type="real_estate",
                options_count=2,
                minutes_until_deadline=30,
            )
        elif notification_type == "auto_selected":
            result = await service.notify_auto_selected(
                slot_id="test-slot-id",
                scheduled_time="12:00",
                content_type="general_dubai",
                selected_option="A",
                confidence=0.85,
                reasoning="Option A has better engagement potential with trending Dubai content.",
            )
        elif notification_type == "publish_success":
            result = await service.notify_publish_success(
                slot_id="test-slot-id",
                scheduled_time="16:00",
                title="Test Post Title - Dubai Real Estate Update",
                selected_by="human",
                message_id_en=12345,
                message_id_ru=12346,
            )
        elif notification_type == "publish_failed":
            result = await service.notify_publish_failed(
                slot_id="test-slot-id",
                scheduled_time="20:00",
                error_message="Network timeout connecting to Telegram API",
                retry_count=3,
            )
        else:
            return {
                "success": False,
                "message": f"Unknown notification type: {notification_type}",
            }

        return {
            "success": result.success,
            "message_id": result.message_id,
            "error": result.error,
        }

    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
        }


@router.post("/telegram/test-publish")
async def test_telegram_publish(
    current_user: User = Depends(get_current_user),
):
    """
    Send a test post to the Telegram channel to verify publishing works.
    This is for testing purposes only and will post a Russian test message.
    """
    try:
        publisher = TelegramPublisher()

        # Create test content (Russian only)
        content = PostContent(
            title_ru="🔧 Тестовое сообщение",
            body_ru="Это автоматическое тестовое сообщение от IDIGOV Content Engine.\n\nЕсли вы видите это, публикация в Telegram работает корректно!\n\n✅ Соединение подтверждено",
            hashtags=["#IDIGOV", "#Test"],
            image_url=None,
            image_local_path=None,
        )

        # Publish to Telegram
        result = await publisher.publish_post(content)

        return {
            "success": result.success,
            "message_id_ru": result.message_id_ru,
            "channel_id": result.channel_id,
            "error": result.error,
        }
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error: {str(e)}",
        }
