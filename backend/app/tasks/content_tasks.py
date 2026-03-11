"""
Celery tasks for content generation and auto-selection.
"""
import asyncio
import json
import logging
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.content_slot import ContentSlot
from app.models.post_option import PostOption
from app.models.scraped_article import ScrapedArticle
from app.services.content.content_generator import ContentGenerator
from app.services.content.image_generator import ImageGenerator
from app.services.content.auto_selector import AutoSelector
from app.services.content.slot_manager import SlotManager, DUBAI_TZ
from app.models.prompt_config import PromptConfig
from app.services.telegram_publisher import TelegramPublisher, PostContent
from app.services.notification_service import send_notification, NotificationType
from app.models.published_post import PublishedPost
from app.tasks.celery_app import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)


def get_async_session():
    """Create a fresh async session for each task."""
    engine = create_async_engine(settings.async_database_url, pool_size=3, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=2)
def create_daily_slots_task(self, target_date_str: str = None):
    """
    Create content slots for a given date.
    """
    if target_date_str:
        target_date = date.fromisoformat(target_date_str)
    else:
        target_date = datetime.now(DUBAI_TZ).date()

    logger.info(f"Creating slots for {target_date}")

    async def _create_slots():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            manager = SlotManager(db)
            slots = await manager.create_daily_slots(target_date)
            return {"slots_created": len(slots), "date": str(target_date)}

    try:
        return run_async(_create_slots())
    except Exception as e:
        logger.error(f"Failed to create daily slots: {e}")
        self.retry(countdown=60, exc=e)


@celery_app.task(bind=True, max_retries=2)
def generate_content_for_slot(self, slot_id: str):
    """
    Generate 2 post options (A and B) for a content slot.
    """
    logger.info(f"Generating content for slot {slot_id}")

    async def _generate():
        AsyncSessionLocal = get_async_session()

        # Step 1: Get slot and articles data
        slot_data = None
        article_dicts = []

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ContentSlot).where(ContentSlot.id == UUID(slot_id))
            )
            slot = result.scalar_one_or_none()

            if not slot:
                return {"error": f"Slot {slot_id} not found"}

            if slot.status == "published":
                return {"error": f"Slot {slot_id} is already published"}

            # Allow regeneration for pending, generating, options_ready, approved, failed
            if slot.status in ["options_ready", "approved", "failed"]:
                # Clear existing options for regeneration
                from sqlalchemy import delete as sql_delete
                from sqlalchemy import update as sql_update

                # First get the option IDs for this slot
                existing_options_result = await db.execute(
                    select(PostOption.id).where(PostOption.slot_id == slot.id)
                )
                existing_option_ids = [row[0] for row in existing_options_result.fetchall()]

                slot.selected_option_id = None
                slot.selected_by = None
                slot.selected_by_user_id = None
                await db.flush()

                # Clear article references to these options (foreign key constraint)
                if existing_option_ids:
                    await db.execute(
                        sql_update(ScrapedArticle)
                        .where(ScrapedArticle.used_in_post_id.in_(existing_option_ids))
                        .values(used_in_post_id=None, is_used=False)
                    )
                    await db.flush()

                # Now delete old options
                await db.execute(
                    sql_delete(PostOption).where(PostOption.slot_id == slot.id)
                )
                await db.commit()
                logger.info(f"Cleared existing options for slot {slot_id} for regeneration")

            # Update status to generating
            slot.status = "generating"
            await db.commit()

            # Store slot data
            slot_data = {
                "id": str(slot.id),
                "content_type": slot.content_type,
                "slot_number": slot.slot_number,
            }

            # Get relevant articles
            manager = SlotManager(db)
            logger.info(f"Fetching articles for content_type={slot.content_type}")
            articles = await manager.get_articles_for_content_type(
                slot.content_type,
                limit=10,
                exclude_used=True
            )

            logger.info(f"Found {len(articles) if articles else 0} articles for slot {slot_id}")

            if not articles:
                slot.status = "failed"
                await db.commit()
                logger.error(f"No articles available for slot {slot_id} - content generation failed")
                return {"error": "No articles available for content generation"}

            # Convert articles to dicts
            article_dicts = [
                {
                    "id": str(a.id),
                    "title": a.title,
                    "summary": a.summary or "",
                    "url": a.url,
                }
                for a in articles
            ]

        # Step 2: Load prompt config from DB
        prompt_config_dict = None
        async with AsyncSessionLocal() as db:
            # Try slot-specific override first, then global
            slot_num = slot_data["slot_number"]
            result = await db.execute(
                select(PromptConfig).where(
                    PromptConfig.scope == "slot_override",
                    PromptConfig.slot_number == slot_num,
                    PromptConfig.is_active == True,
                )
            )
            pc = result.scalar_one_or_none()

            if not pc:
                result = await db.execute(
                    select(PromptConfig).where(
                        PromptConfig.scope == "global",
                        PromptConfig.is_active == True,
                    )
                )
                pc = result.scalar_one_or_none()

            if pc:
                prompt_config_dict = {
                    "system_prompt": pc.system_prompt,
                    "generation_prompt": pc.generation_prompt,
                    "tone": pc.tone,
                    "max_length_chars": pc.max_length_chars,
                    "image_style_prompt": pc.image_style_prompt,
                    "image_aspect_ratio": pc.image_aspect_ratio,
                }
                logger.info(f"Loaded prompt config: scope={pc.scope}, slot={pc.slot_number}")

        # Generate content (outside DB session)
        generator = ContentGenerator()
        image_gen = ImageGenerator(output_dir="generated_images")

        options_to_save = []
        category = "real_estate_news" if slot_data["content_type"] == "real_estate" else "general"

        for label, article_subset in [
            ("A", article_dicts[:5]),
            ("B", article_dicts[5:10] if len(article_dicts) > 5 else article_dicts[:5])
        ]:
            try:
                logger.info(f"Generating post {label} for slot {slot_id}")

                # Generate post content
                post = await generator.generate_post(
                    articles=article_subset,
                    content_type=slot_data["content_type"],
                    category=category,
                    prompt_config=prompt_config_dict,
                )

                # Generate image
                logger.info(f"Generating image for option {label}")
                image_url, image_path, image_base64 = await image_gen.generate_image(
                    prompt=post.image_prompt,
                    category=category,
                    slot_id=slot_id,
                    option_label=label,
                    prompt_config=prompt_config_dict,
                    image_style=post.image_style,
                )

                logger.info(f"Image generated, base64 length: {len(image_base64) if image_base64 else 0}")

                options_to_save.append({
                    "label": label,
                    "post": post,
                    "image_url": image_url,
                    "image_path": image_path,
                    "image_data": image_base64,
                    "source_ids": [a["id"] for a in article_subset],
                    "category": category,
                })

                logger.info(f"Generated option {label} for slot {slot_id} (image: {image_path})")

            except Exception as e:
                logger.error(f"Failed to generate option {label}: {e}")
                import traceback
                traceback.print_exc()
                continue

        # Step 3: Save results (new DB session)
        options_created = []

        async with AsyncSessionLocal() as db:
            # Refresh slot from DB
            result = await db.execute(
                select(ContentSlot).where(ContentSlot.id == UUID(slot_id))
            )
            slot = result.scalar_one_or_none()

            for opt_data in options_to_save:
                # FIRST: Mark articles as used to prevent race conditions
                for aid in opt_data["source_ids"]:
                    art_result = await db.execute(
                        select(ScrapedArticle).where(ScrapedArticle.id == UUID(aid))
                    )
                    article = art_result.scalar_one_or_none()
                    if article:
                        article.is_used = True
                await db.flush()  # Lock articles first

                # THEN: Create PostOption (Russian-only, EN fields empty)
                option = PostOption(
                    slot_id=slot.id,
                    option_label=opt_data["label"],
                    title_en="",  # Empty for Russian-only channel
                    body_en="",   # Empty for Russian-only channel
                    title_ru=opt_data["post"].title_ru,
                    body_ru=opt_data["post"].body_ru,
                    hashtags=json.dumps(opt_data["post"].hashtags),
                    image_prompt=opt_data["post"].image_prompt,
                    image_url=opt_data["image_url"],
                    image_local_path=opt_data["image_path"],
                    image_data=opt_data.get("image_data"),  # Base64 encoded image
                    category=opt_data["category"],
                    content_type=slot_data["content_type"],
                    source_article_ids=json.dumps(opt_data["source_ids"]),
                    ai_quality_score=opt_data["post"].quality_score,
                    image_style=opt_data["post"].image_style,
                )

                db.add(option)
                await db.flush()
                options_created.append(str(option.id))

                # Update article references with the post ID
                for aid in opt_data["source_ids"]:
                    art_result = await db.execute(
                        select(ScrapedArticle).where(ScrapedArticle.id == UUID(aid))
                    )
                    article = art_result.scalar_one_or_none()
                    if article:
                        article.used_in_post_id = option.id
                await db.flush()

            # Update slot status
            if options_created:
                slot.status = "options_ready"
            else:
                slot.status = "failed"

            await db.commit()

            # Get slot info for notification
            scheduled_time = slot.scheduled_time
            content_type = slot.content_type
            approval_deadline = slot.approval_deadline

        # Send notification
        if options_created:
            # Calculate minutes until deadline
            now = datetime.now(DUBAI_TZ)
            minutes_until_deadline = 30  # Default
            if approval_deadline:
                diff = (approval_deadline - now).total_seconds()
                minutes_until_deadline = max(0, int(diff / 60))

            await send_notification(
                NotificationType.OPTIONS_READY,
                slot_id=slot_id,
                scheduled_time=scheduled_time,
                content_type=content_type,
                options_count=len(options_created),
                minutes_until_deadline=minutes_until_deadline,
            )
        else:
            await send_notification(
                NotificationType.GENERATION_FAILED,
                slot_id=slot_id,
                scheduled_time=scheduled_time,
                content_type=content_type,
                error_message="No content options could be generated",
            )

        return {
            "slot_id": slot_id,
            "options_created": options_created,
            "status": "options_ready" if options_created else "failed",
        }

    try:
        return run_async(_generate())
    except Exception as e:
        logger.error(f"Content generation failed for slot {slot_id}: {e}")
        import traceback
        traceback.print_exc()
        self.retry(countdown=120, exc=e)


@celery_app.task(bind=True, max_retries=1)
def auto_select_for_slot(self, slot_id: str):
    """
    Auto-select the best option for a slot when deadline passes.
    """
    logger.info(f"Auto-selecting for slot {slot_id}")

    async def _auto_select():
        AsyncSessionLocal = get_async_session()

        # Step 1: Get slot and options
        option_dicts = []
        slot_content_type = None
        slot_scheduled_time = None

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ContentSlot)
                .options(selectinload(ContentSlot.options))
                .where(ContentSlot.id == UUID(slot_id))
            )
            slot = result.scalar_one_or_none()

            if not slot:
                return {"error": f"Slot {slot_id} not found"}

            if slot.selected_option_id:
                return {"error": "Slot already has a selection"}

            if not slot.options:
                return {"error": "No options available for selection"}

            slot_content_type = slot.content_type
            slot_scheduled_time = slot.scheduled_time

            option_dicts = [
                {
                    "option_label": opt.option_label,
                    "title_en": opt.title_en,
                    "body_en": opt.body_en,
                    "title_ru": opt.title_ru,
                    "body_ru": opt.body_ru,
                    "hashtags": json.loads(opt.hashtags) if opt.hashtags else [],
                    "image_prompt": opt.image_prompt,
                    "ai_quality_score": opt.ai_quality_score,
                    "id": str(opt.id),
                }
                for opt in slot.options
            ]

        # Step 2: Run AI selection (outside DB session)
        selector = AutoSelector()
        selected_label, reasoning, confidence = await selector.select_best_option(
            options=option_dicts,
            content_type=slot_content_type,
            slot_time=slot_scheduled_time,
        )

        # Find the selected option ID
        selected_option_id = next(
            (opt["id"] for opt in option_dicts if opt["option_label"] == selected_label),
            option_dicts[0]["id"]
        )

        # Step 3: Update slot (new DB session)
        async with AsyncSessionLocal() as db:
            manager = SlotManager(db)
            await manager.update_slot_status(
                slot_id=UUID(slot_id),
                status="approved",
                selected_option_id=UUID(selected_option_id),
                selected_by="ai",
            )

        # Send notification about auto-selection
        await send_notification(
            NotificationType.AUTO_SELECTED,
            slot_id=slot_id,
            scheduled_time=slot_scheduled_time,
            content_type=slot_content_type,
            selected_option=selected_label,
            confidence=confidence,
            reasoning=reasoning,
        )

        return {
            "slot_id": slot_id,
            "selected_option": selected_label,
            "selected_option_id": selected_option_id,
            "reasoning": reasoning,
            "confidence": confidence,
        }

    try:
        return run_async(_auto_select())
    except Exception as e:
        logger.error(f"Auto-selection failed for slot {slot_id}: {e}")
        self.retry(countdown=60, exc=e)


@celery_app.task(bind=True)
def generate_all_pending_content(self):
    """
    Generate content for all pending slots.
    """
    logger.info("Generating content for all pending slots")

    async def _generate_all():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            manager = SlotManager(db)
            pending_slots = await manager.get_pending_slots()

            results = []
            for slot in pending_slots:
                task = generate_content_for_slot.delay(str(slot.id))
                results.append({
                    "slot_id": str(slot.id),
                    "task_id": task.id,
                })

            return {
                "slots_queued": len(results),
                "tasks": results,
            }

    return run_async(_generate_all())


@celery_app.task(bind=True)
def check_and_auto_select(self):
    """
    Check for slots past deadline and auto-select if needed.
    """
    logger.info("Checking for slots needing auto-selection")

    async def _check_slots():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            manager = SlotManager(db)
            slots = await manager.get_slots_needing_selection()

            results = []
            for slot in slots:
                task = auto_select_for_slot.delay(str(slot.id))
                results.append({
                    "slot_id": str(slot.id),
                    "task_id": task.id,
                })

            return {
                "slots_processed": len(results),
                "tasks": results,
            }

    return run_async(_check_slots())


@celery_app.task(bind=True, max_retries=2)
def publish_scheduled_slot(self, slot_id: str = None, slot_number: int = None):
    """
    Publish an approved slot to Telegram.

    Args:
        slot_id: Direct slot UUID (for manual publish via API)
        slot_number: Slot number 1-5 (for scheduled publish via Celery beat)
    """
    import redis
    from datetime import timedelta

    logger.info(f"Publishing task triggered, slot_id={slot_id}, slot_number={slot_number}")

    # Create Redis lock to prevent duplicate publishing
    redis_client = redis.from_url(settings.effective_redis_url)
    lock_key = f"publish_lock:{slot_id or f'slot_{slot_number}'}:{datetime.now(DUBAI_TZ).date()}"
    lock = redis_client.lock(lock_key, timeout=300, blocking_timeout=5)

    if not lock.acquire(blocking=False):
        logger.warning(f"Could not acquire lock {lock_key}, another worker is publishing")
        return {"status": "skipped", "reason": "lock_not_acquired"}

    try:
        result = run_async(_do_publish(slot_id, slot_number))
        return result
    except Exception as e:
        logger.error(f"Publishing task failed: {e}")
        import traceback
        traceback.print_exc()
        self.retry(countdown=60, exc=e)
    finally:
        try:
            lock.release()
        except Exception:
            pass  # Lock may have expired


def _do_publish(slot_id: str = None, slot_number: int = None):
    """Inner publish function."""
    async def _publish():
        from sqlalchemy import func
        AsyncSessionLocal = get_async_session()

        async with AsyncSessionLocal() as db:
            slots_to_publish = []

            if slot_id:
                # Publish specific slot by ID (manual publish)
                result = await db.execute(
                    select(ContentSlot)
                    .options(selectinload(ContentSlot.options))
                    .where(ContentSlot.id == UUID(slot_id))
                )
                slot = result.scalar_one_or_none()
                if slot:
                    slots_to_publish = [slot]
            elif slot_number:
                # Scheduled publish: find slot by slot_number + today's date
                now = datetime.now(DUBAI_TZ)
                today = now.date()

                result = await db.execute(
                    select(ContentSlot)
                    .options(selectinload(ContentSlot.options))
                    .where(
                        ContentSlot.status == "approved",
                        ContentSlot.slot_number == slot_number,
                        ContentSlot.scheduled_date == today,
                    )
                    .order_by(ContentSlot.created_at)
                    .limit(1)
                )
                slot = result.scalars().first()
                if slot:
                    slots_to_publish = [slot]
                    logger.info(f"Found slot {slot.id} for slot_number={slot_number} on {today}")
            else:
                logger.warning("No slot_id or slot_number provided, nothing to publish")
                return {"published": 0, "message": "No slot identifier provided"}

            if not slots_to_publish:
                logger.info("No approved slots to publish at this time")
                return {"published": 0, "message": "No slots to publish"}

            # Initialize publisher
            try:
                publisher = TelegramPublisher()
            except ValueError as e:
                logger.error(f"Telegram not configured: {e}")
                return {"error": str(e)}

            results = []
            for slot in slots_to_publish:
                # IDEMPOTENCY CHECK: Skip if already published
                if slot.published_post_id:
                    logger.info(f"Skipping slot {slot.id} - already published (post_id={slot.published_post_id})")
                    results.append({
                        "slot_id": str(slot.id),
                        "success": True,
                        "skipped": True,
                        "reason": "already_published",
                    })
                    continue

                if slot.status != "approved":
                    logger.info(f"Skipping slot {slot.id} - status is {slot.status}")
                    continue

                if not slot.selected_option_id:
                    logger.warning(f"Slot {slot.id} has no selected option")
                    continue

                # Get selected option
                option = next(
                    (opt for opt in slot.options if opt.id == slot.selected_option_id),
                    None
                )

                if not option:
                    logger.warning(f"Selected option not found for slot {slot.id}")
                    continue

                # Parse hashtags
                hashtags = []
                if option.hashtags:
                    try:
                        hashtags = json.loads(option.hashtags)
                    except json.JSONDecodeError:
                        hashtags = []

                # Create post content (Russian-only)
                content = PostContent(
                    title_en="",  # Empty for Russian-only channel
                    body_en="",   # Empty for Russian-only channel
                    title_ru=option.title_ru,
                    body_ru=option.body_ru,
                    hashtags=hashtags,
                    image_url=option.image_url,
                    image_local_path=option.image_local_path,
                    image_data=option.image_data,  # Base64 encoded image
                )

                # Publish
                logger.info(f"Publishing slot {slot.id} to Telegram")
                publish_result = await publisher.publish_post(content)

                if publish_result.success:
                    # Create PublishedPost record (Russian-only)
                    published_post = PublishedPost(
                        slot_id=slot.id,
                        option_id=option.id,
                        posted_title=option.title_ru,
                        posted_body=option.body_ru,
                        posted_language="ru",
                        posted_image_url=option.image_url,
                        telegram_message_id=publish_result.message_id_ru,
                        telegram_channel_id=publish_result.channel_id,
                        selected_by=slot.selected_by or "ai",
                        selected_by_user_id=slot.selected_by_user_id,
                    )
                    db.add(published_post)
                    await db.flush()

                    # Update slot status
                    slot.status = "published"
                    slot.published_post_id = published_post.id

                    results.append({
                        "slot_id": str(slot.id),
                        "success": True,
                        "message_id_en": publish_result.message_id_en,
                        "message_id_ru": publish_result.message_id_ru,
                    })
                    logger.info(f"Successfully published slot {slot.id}")

                    # Send success notification
                    await send_notification(
                        NotificationType.PUBLISH_SUCCESS,
                        slot_id=str(slot.id),
                        scheduled_time=slot.scheduled_time,
                        title=option.title_en,
                        selected_by=slot.selected_by or "ai",
                        message_id_en=publish_result.message_id_en,
                        message_id_ru=publish_result.message_id_ru,
                    )
                else:
                    results.append({
                        "slot_id": str(slot.id),
                        "success": False,
                        "error": publish_result.error,
                    })
                    logger.error(f"Failed to publish slot {slot.id}: {publish_result.error}")

                    # Send failure notification
                    await send_notification(
                        NotificationType.PUBLISH_FAILED,
                        slot_id=str(slot.id),
                        scheduled_time=slot.scheduled_time,
                        error_message=publish_result.error or "Unknown error",
                        retry_count=0,
                    )

            await db.commit()

            return {
                "published": sum(1 for r in results if r.get("success")),
                "failed": sum(1 for r in results if not r.get("success")),
                "results": results,
            }

    return _publish()
