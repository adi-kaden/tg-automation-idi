"""
Celery tasks for content generation and auto-selection.
"""
import asyncio
import json
import logging
from datetime import date, datetime, timedelta
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
from app.services.alert_service import send_alert
from app.models.published_post import PublishedPost
from app.models.fallback_post import FallbackPost
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


def try_acquire_redis_lock(key: str, ttl_seconds: int = 300) -> tuple[bool, str]:
    """
    Try to acquire a Redis lock. Returns (acquired, status).

    status is one of: "acquired", "held_by_other", "redis_unavailable".
    Never raises — callers can decide whether to skip or proceed when Redis
    is unavailable (duplicate risk vs. availability tradeoff).
    """
    try:
        import redis as redis_lib
        client = redis_lib.from_url(settings.effective_redis_url, socket_timeout=3)
        if client.set(key, "1", nx=True, ex=ttl_seconds):
            return True, "acquired"
        return False, "held_by_other"
    except Exception as e:
        logger.error(f"Redis lock {key} unavailable: {e}")
        return False, "redis_unavailable"


async def _fetch_recent_published_posts(session) -> list[dict]:
    """Fetch posts published in the last 3 days for topic deduplication."""
    try:
        from sqlalchemy import func
        cutoff = func.now() - timedelta(days=3)
        result = await session.execute(
            select(PublishedPost)
            .where(PublishedPost.published_at >= cutoff)
            .order_by(PublishedPost.published_at.desc())
        )
        posts = result.scalars().all()
        return [
            {
                "title": p.posted_title,
                "body_snippet": (p.posted_body or "")[:150],
                "published_at": str(p.published_at),
            }
            for p in posts
        ]
    except Exception as e:
        logger.error(f"Failed to fetch recent posts for dedup: {e}")
        return []


async def _fetch_todays_generated_topics(session, exclude_slot_id: str = None) -> list[dict]:
    """Fetch titles/bodies from PostOptions generated today (not yet published).
    This provides cross-slot topic awareness within the same day."""
    try:
        today = datetime.now(DUBAI_TZ).date()
        query = (
            select(PostOption)
            .join(ContentSlot, PostOption.slot_id == ContentSlot.id)
            .where(ContentSlot.scheduled_date == today)
        )
        if exclude_slot_id:
            query = query.where(ContentSlot.id != UUID(exclude_slot_id))
        result = await session.execute(query)
        options = result.scalars().all()
        return [
            {
                "title": o.title_ru,
                "body_snippet": (o.body_ru or "")[:150],
            }
            for o in options
        ]
    except Exception as e:
        logger.error(f"Failed to fetch today's generated topics: {e}")
        return []


@celery_app.task(bind=True)
def ensure_todays_pipeline(self):
    """
    Startup catch-up: ensure today's slots exist and content generation has run.
    Called on worker startup and can be called manually to recover from downtime.
    """
    logger.info("Ensuring today's pipeline is running")

    async def _ensure():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            today = datetime.now(DUBAI_TZ).date()
            result = await db.execute(
                select(ContentSlot).where(ContentSlot.scheduled_date == today)
            )
            slots = result.scalars().all()

            if not slots:
                logger.warning(f"No slots for {today} — creating now (startup catch-up)")
                manager = SlotManager(db)
                slots = await manager.create_daily_slots(today)
                await db.commit()
                logger.info(f"Created {len(slots)} slots for {today}")
                # Trigger content generation
                generate_all_pending_content.apply_async(countdown=10)
                return {"action": "created_slots", "count": len(slots)}

            pending = [s for s in slots if s.status == "pending"]
            generating = [s for s in slots if s.status == "generating"]

            # Reset stuck "generating" slots (from a previous worker crash)
            if generating:
                for slot in generating:
                    logger.warning(f"Resetting stuck slot {slot.id} from 'generating' to 'pending'")
                    slot.status = "pending"
                await db.commit()
                pending.extend(generating)

            if pending:
                logger.info(f"Found {len(pending)} pending slots — triggering content generation")
                generate_all_pending_content.apply_async(countdown=10)
                return {"action": "triggered_generation", "pending": len(pending)}

            logger.info(f"Today's pipeline looks healthy: {len(slots)} slots exist")
            return {"action": "none_needed", "slots": len(slots)}

    return run_async(_ensure())


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

            # Clean up existing options for regeneration.
            # Status may already be "generating" (set by the API endpoint).
            if slot.status in ["options_ready", "approved", "failed", "generating"]:
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
                "album_mode": getattr(slot, "album_mode", False),
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

                await send_notification(
                    NotificationType.GENERATION_FAILED,
                    slot_id=slot_id,
                    scheduled_time=slot.scheduled_time,
                    content_type=slot.content_type,
                    error_message="No articles available for content generation",
                )

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
                    "voice_preset": getattr(pc, "voice_preset", "professional"),
                }
                logger.info(f"Loaded prompt config: scope={pc.scope}, slot={pc.slot_number}")

        # Fetch recent published posts for topic deduplication
        recent_posts = []
        todays_topics = []
        async with AsyncSessionLocal() as db:
            recent_posts = await _fetch_recent_published_posts(db)
            todays_topics = await _fetch_todays_generated_topics(db, exclude_slot_id=slot_id)
        # Merge: today's generated options first (highest priority), then published
        all_dedup_context = todays_topics + recent_posts
        logger.info(f"Dedup context: {len(todays_topics)} today's topics + {len(recent_posts)} recent published")

        # Generate content (outside DB session)
        generator = ContentGenerator()
        image_gen = ImageGenerator(output_dir="generated_images")

        options_to_save = []
        category = "real_estate_news" if slot_data["content_type"] == "real_estate" else "general"

        import random
        if len(article_dicts) > 5:
            option_pairs = [
                ("A", article_dicts[:5]),
                ("B", article_dicts[5:10]),
            ]
        else:
            # Shuffle for B so Claude sees a different article ordering
            shuffled = article_dicts.copy()
            random.shuffle(shuffled)
            option_pairs = [
                ("A", article_dicts),
                ("B", shuffled),
            ]

        # Extract voice_preset and album_mode once (same for both options)
        voice_preset = "professional"
        if prompt_config_dict:
            voice_preset = prompt_config_dict.get("voice_preset", "professional")
        album_mode = slot_data.get("album_mode", False)

        for idx, (label, article_subset) in enumerate(option_pairs):
            # Space out Claude API calls to stay under per-minute token limit
            if idx > 0:
                logger.info(f"Waiting 60s before generating option {label} to avoid rate limits")
                await asyncio.sleep(60)

            try:
                logger.info(f"Generating post {label} for slot {slot_id}")

                # For option B, add option A's generated title to dedup context
                effective_dedup = list(all_dedup_context)
                if idx > 0 and options_to_save:
                    prev = options_to_save[-1]["post"]
                    effective_dedup.insert(0, {
                        "title": prev.title_ru,
                        "body_snippet": (prev.body_ru or "")[:150],
                    })

                # Generate post content
                post = await generator.generate_post(
                    articles=article_subset,
                    content_type=slot_data["content_type"],
                    category=category,
                    prompt_config=prompt_config_dict,
                    recent_posts=effective_dedup,
                    voice_preset=voice_preset,
                    album_mode=album_mode,
                )

                # Generate image(s)
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

                # Generate album images if in album mode
                album_image_prompts_json = None
                album_images_data_json = None
                if album_mode and post.album_image_prompts:
                    logger.info(f"Album mode: generating {len(post.album_image_prompts)} additional images")
                    album_images = await image_gen.generate_album_images(
                        prompts=post.album_image_prompts,
                        category=category,
                        slot_id=slot_id,
                        option_label=label,
                        prompt_config=prompt_config_dict,
                        image_style=post.image_style,
                    )
                    album_image_prompts_json = json.dumps(post.album_image_prompts)
                    album_base64_list = [img[2] for img in album_images if img[2]]
                    if album_base64_list:
                        album_images_data_json = json.dumps(album_base64_list)
                    logger.info(f"Album images generated: {len(album_base64_list)} successful")

                options_to_save.append({
                    "label": label,
                    "post": post,
                    "image_url": image_url,
                    "image_path": image_path,
                    "image_data": image_base64,
                    "album_image_prompts": album_image_prompts_json,
                    "album_images_data": album_images_data_json,
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
                    album_image_prompts=opt_data.get("album_image_prompts"),
                    album_images_data=opt_data.get("album_images_data"),
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
            # Send alert to admin
            send_alert(
                "Content Generation Failed",
                details={
                    "Slot": slot_id[:8],
                    "Type": content_type,
                    "Schedule": str(scheduled_time),
                },
                error="Both options A and B failed to generate",
            )
            # Raise so Celery retry mechanism kicks in
            raise RuntimeError(f"All content options failed for slot {slot_id}")

        return {
            "slot_id": slot_id,
            "options_created": options_created,
            "status": "options_ready",
        }

    try:
        return run_async(_generate())
    except Exception as e:
        logger.error(f"Content generation failed for slot {slot_id}: {e}")
        import traceback
        traceback.print_exc()
        self.retry(countdown=180, exc=e)


@celery_app.task(bind=True, max_retries=3)
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

        # Fetch recent published posts for dedup context
        recent_posts = []
        async with AsyncSessionLocal() as db:
            recent_posts = await _fetch_recent_published_posts(db)

        # Step 2: Run AI selection (outside DB session)
        selector = AutoSelector()
        selected_label, reasoning, confidence = await selector.select_best_option(
            options=option_dicts,
            content_type=slot_content_type,
            slot_time=slot_scheduled_time,
            recent_posts=recent_posts,
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
        # Exponential backoff: 60s, 180s, 420s
        countdown = 60 * (3 ** self.request.retries)
        self.retry(countdown=countdown, exc=e)


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
            for i, slot in enumerate(pending_slots):
                # Stagger each slot by 3 minutes to avoid API rate limits
                # Each slot needs ~2 min (60s gap between A and B + generation time)
                delay_seconds = i * 180
                task = generate_content_for_slot.apply_async(
                    args=[str(slot.id)],
                    countdown=delay_seconds,
                )
                results.append({
                    "slot_id": str(slot.id),
                    "task_id": task.id,
                    "delay_seconds": delay_seconds,
                })
                logger.info(f"Queued slot {slot.id} with {delay_seconds}s delay")

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
    logger.info(f"Publishing task triggered, slot_id={slot_id}, slot_number={slot_number}")

    try:
        result = run_async(_do_publish(slot_id, slot_number))
        return result
    except Exception as e:
        logger.error(f"Publishing task failed: {e}")
        import traceback
        traceback.print_exc()
        self.retry(countdown=60, exc=e)


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
                # Scheduled publish: find slot by slot_number + time window
                # Use scheduled_at window instead of scheduled_date to handle
                # slot 5 (00:00 Dubai) which crosses the date boundary
                now = datetime.now(DUBAI_TZ)

                result = await db.execute(
                    select(ContentSlot)
                    .options(selectinload(ContentSlot.options))
                    .where(
                        ContentSlot.status == "approved",
                        ContentSlot.slot_number == slot_number,
                        ContentSlot.scheduled_at.between(
                            now - timedelta(hours=1),
                            now + timedelta(minutes=30),
                        ),
                    )
                    .order_by(ContentSlot.scheduled_at.desc())
                    .limit(1)
                )
                slot = result.scalars().first()
                if slot:
                    slots_to_publish = [slot]
                    logger.info(f"Found slot {slot.id} for slot_number={slot_number} (scheduled_at={slot.scheduled_at})")
            else:
                logger.warning("No slot_id or slot_number provided, nothing to publish")
                return {"published": 0, "message": "No slot identifier provided"}

            if not slots_to_publish:
                msg = f"No approved slot found for slot {slot_number or slot_id} at publish time"
                logger.warning(msg)

                if slot_number:
                    from app.services.content.slot_manager import SLOT_SCHEDULE
                    slot_time = next(
                        (s["time"] for s in SLOT_SCHEDULE if s["slot_number"] == slot_number),
                        f"slot {slot_number}"
                    )
                    await send_notification(
                        NotificationType.PUBLISH_FAILED,
                        slot_id="N/A",
                        scheduled_time=slot_time,
                        error_message=msg,
                        retry_count=0,
                    )

                return {"published": 0, "message": msg}

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

                # Acquire slot-specific Redis lock to prevent duplicate publishing.
                # On Redis outage we skip rather than risk a duplicate — the
                # watchdog or next beat tick will re-attempt once Redis is back.
                slot_lock_key = f"publish_slot:{slot.id}"
                acquired, lock_status = try_acquire_redis_lock(slot_lock_key, ttl_seconds=300)
                if not acquired:
                    logger.info(f"Skipping slot {slot.id} - lock status: {lock_status}")
                    if lock_status == "redis_unavailable":
                        send_alert(
                            "Publish Skipped — Redis Unavailable",
                            details={
                                "Slot": str(slot.id)[:8],
                                "Slot #": slot.slot_number,
                                "Schedule": slot.scheduled_time,
                            },
                            error="Redis lock could not be acquired; skipping to avoid duplicate publish.",
                        )
                    results.append({
                        "slot_id": str(slot.id),
                        "success": False,
                        "skipped": True,
                        "reason": lock_status,
                    })
                    continue

                if slot.status != "approved":
                    # The watchdog will attempt recovery for options_ready slots.
                    # Still alert so ops knows the scheduled publish bailed.
                    logger.warning(f"Slot {slot.id} status is {slot.status}, not approved — cannot publish")
                    send_alert(
                        "Publish Skipped — Slot Not Approved",
                        details={
                            "Slot #": slot.slot_number,
                            "Schedule": slot.scheduled_time,
                            "Status": slot.status,
                        },
                        error="Slot reached publish time without being approved. Watchdog will attempt recovery.",
                    )
                    results.append({
                        "slot_id": str(slot.id),
                        "success": False,
                        "skipped": True,
                        "reason": f"status_{slot.status}",
                    })
                    continue

                if not slot.selected_option_id:
                    logger.warning(f"Slot {slot.id} has no selected option")
                    send_alert(
                        "Publish Skipped — No Option Selected",
                        details={
                            "Slot #": slot.slot_number,
                            "Schedule": slot.scheduled_time,
                        },
                        error="Slot is marked approved but has no selected_option_id. Watchdog will attempt recovery.",
                    )
                    results.append({
                        "slot_id": str(slot.id),
                        "success": False,
                        "skipped": True,
                        "reason": "no_selection",
                    })
                    continue

                # Get selected option
                option = next(
                    (opt for opt in slot.options if opt.id == slot.selected_option_id),
                    None
                )

                if not option:
                    logger.warning(f"Selected option not found for slot {slot.id}")
                    send_alert(
                        "Publish Skipped — Selected Option Missing",
                        details={
                            "Slot #": slot.slot_number,
                            "Schedule": slot.scheduled_time,
                            "Selected option": str(slot.selected_option_id)[:8],
                        },
                        error="selected_option_id is set but the PostOption record is missing. Watchdog will attempt recovery.",
                    )
                    results.append({
                        "slot_id": str(slot.id),
                        "success": False,
                        "skipped": True,
                        "reason": "option_missing",
                    })
                    continue

                # Parse hashtags
                hashtags = []
                if option.hashtags:
                    try:
                        hashtags = json.loads(option.hashtags)
                    except json.JSONDecodeError:
                        hashtags = []

                # Parse album images if present
                album_images = None
                if getattr(option, "album_images_data", None):
                    try:
                        album_images = json.loads(option.album_images_data)
                    except json.JSONDecodeError:
                        album_images = None

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
                    album_images_data=album_images,
                )

                # Publish (album or single post)
                logger.info(f"Publishing slot {slot.id} to Telegram")
                if album_images and len(album_images) > 0:
                    publish_result = await publisher.publish_album(content)
                else:
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


@celery_app.task(bind=True)
def publish_overdue_slots(self):
    """Catch-up: publish any approved slots past their scheduled time."""

    async def _publish_overdue():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            now = datetime.now(DUBAI_TZ)
            cutoff = now - timedelta(hours=6)
            result = await db.execute(
                select(ContentSlot)
                .where(
                    ContentSlot.status == "approved",
                    ContentSlot.scheduled_at < now,
                    ContentSlot.scheduled_at > cutoff,
                    ContentSlot.published_post_id.is_(None),
                )
                .order_by(ContentSlot.scheduled_at)
            )
            overdue_slots = result.scalars().all()

            if not overdue_slots:
                return {"overdue": 0}

            for slot in overdue_slots:
                logger.warning(
                    f"Found overdue approved slot {slot.id} "
                    f"(scheduled_at={slot.scheduled_at}). Publishing now."
                )
                publish_scheduled_slot.delay(slot_id=str(slot.id))

            return {"overdue": len(overdue_slots)}

    return run_async(_publish_overdue())


# ==================== Watchdog & Fallback ====================

async def _publish_fallback_for_slot(db, slot) -> tuple[bool, str]:
    """
    Publish an evergreen fallback post for a slot that couldn't be recovered.
    Returns (success, detail) where detail describes which fallback or why it failed.
    """
    from sqlalchemy import nulls_first

    # Prefer fallbacks matching slot.content_type; then "any"; then ANY active.
    async def _pick():
        result = await db.execute(
            select(FallbackPost)
            .where(
                FallbackPost.is_active == True,
                FallbackPost.content_type.in_([slot.content_type, "any"]),
            )
            .order_by(
                FallbackPost.times_used.asc(),
                nulls_first(FallbackPost.last_used_at.asc()),
            )
            .limit(1)
        )
        picked = result.scalar_one_or_none()
        if picked:
            return picked
        result = await db.execute(
            select(FallbackPost)
            .where(FallbackPost.is_active == True)
            .order_by(
                FallbackPost.times_used.asc(),
                nulls_first(FallbackPost.last_used_at.asc()),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    fb = await _pick()
    if not fb:
        return False, "no_fallback_posts_configured"

    try:
        publisher = TelegramPublisher()
    except ValueError as e:
        return False, f"telegram_not_configured: {e}"

    hashtags = []
    if fb.hashtags:
        try:
            hashtags = json.loads(fb.hashtags)
        except (json.JSONDecodeError, TypeError):
            hashtags = []

    content = PostContent(
        title_ru=fb.title_ru,
        body_ru=fb.body_ru,
        hashtags=hashtags,
        image_data=fb.image_data,
    )

    publish_result = await publisher.publish_post(content)
    if not publish_result.success:
        return False, f"telegram_error: {publish_result.error}"

    # Record the publish so channel history + analytics stay consistent.
    published_post = PublishedPost(
        slot_id=slot.id,
        option_id=None,
        posted_title=fb.title_ru,
        posted_body=fb.body_ru,
        posted_language="ru",
        telegram_message_id=publish_result.message_id_ru,
        telegram_channel_id=publish_result.channel_id,
        selected_by="fallback",
    )
    db.add(published_post)
    await db.flush()

    fb.times_used += 1
    fb.last_used_at = datetime.now(DUBAI_TZ)

    slot.status = "published"
    slot.published_post_id = published_post.id

    await db.commit()

    logger.info(
        f"Published fallback {fb.id} for slot {slot.id}, "
        f"msg_id={publish_result.message_id_ru}"
    )
    return True, f"fallback_{str(fb.id)[:8]}"


async def _watchdog_recover_slot(db, slot, now) -> dict:
    """
    Inspect a single overdue slot and attempt recovery in priority order.
    Uses a per-slot Redis lock so concurrent watchdog ticks don't collide.
    """
    overdue_seconds = int((now - slot.scheduled_at).total_seconds())
    slot_label = f"#{slot.slot_number} ({slot.scheduled_time})"

    watchdog_lock_key = f"watchdog_slot:{slot.id}"
    acquired, lock_status = try_acquire_redis_lock(watchdog_lock_key, ttl_seconds=120)
    if not acquired:
        logger.debug(f"Watchdog skipping slot {slot.id} - {lock_status}")
        return {"slot_id": str(slot.id), "action": "skipped", "reason": lock_status}

    logger.info(
        f"Watchdog inspecting slot {slot_label} "
        f"(overdue {overdue_seconds}s, status={slot.status})"
    )

    # Strategy 1: approved + selected → re-trigger publish task (lock-aware idempotent).
    if slot.status == "approved" and slot.selected_option_id:
        publish_scheduled_slot.delay(slot_id=str(slot.id))
        send_alert(
            "Watchdog: Retrying overdue publish",
            details={
                "Slot": slot_label,
                "Status": slot.status,
                "Overdue": f"{overdue_seconds}s",
            },
            error="Slot was approved but not published — re-triggering publish task.",
        )
        return {"slot_id": str(slot.id), "action": "retriggered_publish"}

    # Strategy 2: options_ready without selection → force inline auto-select + publish.
    if slot.status == "options_ready" and not slot.selected_option_id:
        try:
            result = await db.execute(
                select(ContentSlot)
                .options(selectinload(ContentSlot.options))
                .where(ContentSlot.id == slot.id)
            )
            slot_full = result.scalar_one_or_none()

            if slot_full and slot_full.options:
                option_dicts = [
                    {
                        "option_label": opt.option_label,
                        "title_ru": opt.title_ru,
                        "body_ru": opt.body_ru,
                        "title_en": opt.title_en,
                        "body_en": opt.body_en,
                        "hashtags": json.loads(opt.hashtags) if opt.hashtags else [],
                        "image_prompt": opt.image_prompt,
                        "ai_quality_score": opt.ai_quality_score,
                        "id": str(opt.id),
                    }
                    for opt in slot_full.options
                ]

                selector = AutoSelector()
                selected_label, reasoning, confidence = await selector.select_best_option(
                    options=option_dicts,
                    content_type=slot_full.content_type,
                    slot_time=slot_full.scheduled_time,
                    recent_posts=[],
                )
                selected_option_id = next(
                    (opt["id"] for opt in option_dicts if opt["option_label"] == selected_label),
                    option_dicts[0]["id"],
                )

                slot_full.status = "approved"
                slot_full.selected_option_id = UUID(selected_option_id)
                slot_full.selected_by = "ai"
                await db.commit()

                publish_scheduled_slot.delay(slot_id=str(slot.id))
                send_alert(
                    "Watchdog: Forced auto-select + publish",
                    details={
                        "Slot": slot_label,
                        "Selected": selected_label,
                        "Confidence": f"{int(confidence * 100)}%",
                        "Overdue": f"{overdue_seconds}s",
                    },
                    error="Slot reached publish window without selection — forced AI selection.",
                )
                return {
                    "slot_id": str(slot.id),
                    "action": "forced_selection",
                    "selected": selected_label,
                }
        except Exception as e:
            logger.error(f"Watchdog inline auto-select failed for {slot.id}: {e}")
            await db.rollback()
            # Fall through to fallback.

    # Strategy 3: broken state or inline select failed → publish fallback content.
    # Only engage fallback after 3 min overdue to give earlier strategies a chance.
    if overdue_seconds >= 180:
        try:
            ok, detail = await _publish_fallback_for_slot(db, slot)
        except Exception as e:
            logger.error(f"Fallback publish raised for slot {slot.id}: {e}")
            await db.rollback()
            ok, detail = False, str(e)

        if ok:
            send_alert(
                "Watchdog: Fallback content published",
                details={
                    "Slot": slot_label,
                    "Previous status": slot.status,
                    "Overdue": f"{overdue_seconds}s",
                    "Fallback": detail,
                },
                error="Live content pipeline failed — evergreen fallback used. Channel not silent.",
            )
            return {"slot_id": str(slot.id), "action": "fallback_published", "detail": detail}

        send_alert(
            "Watchdog: CRITICAL — recovery failed",
            details={
                "Slot": slot_label,
                "Status": slot.status,
                "Overdue": f"{overdue_seconds}s",
                "Reason": detail,
            },
            error="Cannot recover this slot. Fallback library may be empty. Manual intervention required.",
        )
        return {"slot_id": str(slot.id), "action": "critical_failure", "detail": detail}

    return {"slot_id": str(slot.id), "action": "waiting", "overdue": overdue_seconds}


@celery_app.task(bind=True)
def watchdog_check_slots(self):
    """
    Runs every minute. For each slot whose scheduled_at was within the last
    15 minutes and which has not published, apply the recovery ladder:

      1. approved+selected → re-trigger publish
      2. options_ready without selection → force auto-select + publish
      3. broken state → publish evergreen fallback content
      4. still broken → critical alert to admin

    Also writes a heartbeat to Redis so external monitors can detect when
    beat/worker has been silent.
    """
    # Heartbeat (never let an exception here sink the task).
    try:
        import redis as redis_lib
        client = redis_lib.from_url(settings.effective_redis_url, socket_timeout=3)
        client.set("watchdog:last_tick", datetime.utcnow().isoformat(), ex=900)
    except Exception as e:
        logger.warning(f"Watchdog heartbeat write failed: {e}")

    async def _check():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            now = datetime.now(DUBAI_TZ)
            cutoff = now - timedelta(minutes=15)

            result = await db.execute(
                select(ContentSlot)
                .where(
                    ContentSlot.scheduled_at <= now,
                    ContentSlot.scheduled_at > cutoff,
                    ContentSlot.published_post_id.is_(None),
                )
                .order_by(ContentSlot.scheduled_at)
            )
            overdue = result.scalars().all()

            if not overdue:
                return {"checked": 0}

            actions = []
            for slot in overdue:
                try:
                    actions.append(await _watchdog_recover_slot(db, slot, now))
                except Exception as e:
                    logger.error(f"Watchdog recovery raised for slot {slot.id}: {e}")
                    import traceback
                    traceback.print_exc()
                    actions.append({"slot_id": str(slot.id), "action": "error", "error": str(e)[:200]})

            return {"checked": len(overdue), "actions": actions}

    return run_async(_check())


@celery_app.task(bind=True)
def send_daily_digest(self):
    """
    23:55 Dubai (19:55 UTC): summarize today's pipeline and send a digest to the
    admin alert chat. Confirms the system is alive even on all-green days, and
    surfaces partial failures that individual alerts might have obscured.
    """
    logger.info("Building daily digest")

    async def _digest():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            today = datetime.now(DUBAI_TZ).date()

            slots_result = await db.execute(
                select(ContentSlot)
                .where(ContentSlot.scheduled_date == today)
                .order_by(ContentSlot.slot_number)
            )
            slots = slots_result.scalars().all()

            published_post_ids = [s.published_post_id for s in slots if s.published_post_id]
            fallback_count = 0
            human_count = 0
            ai_count = 0
            if published_post_ids:
                pp_result = await db.execute(
                    select(PublishedPost).where(PublishedPost.id.in_(published_post_ids))
                )
                for pp in pp_result.scalars().all():
                    if pp.selected_by == "fallback":
                        fallback_count += 1
                    elif pp.selected_by == "human":
                        human_count += 1
                    else:
                        ai_count += 1

            total = len(slots)
            published = sum(1 for s in slots if s.status == "published")
            failed = sum(1 for s in slots if s.status == "failed")
            pending = total - published - failed

            details = {
                "Date": str(today),
                "Published": f"{published}/{total}",
                "By human": human_count,
                "By AI": ai_count,
                "By fallback": fallback_count,
                "Failed": failed,
                "Still pending": pending,
            }

            # Choose severity icon based on outcome
            if published == total and fallback_count == 0:
                title = "Daily Digest — All Good"
                error = None
            elif published == total and fallback_count > 0:
                title = "Daily Digest — Published with Fallbacks"
                error = f"{fallback_count} slot(s) needed evergreen fallback content."
            else:
                title = "Daily Digest — Issues"
                error = f"{total - published} slot(s) did not publish live content."

            send_alert(title, details=details, error=error)

            return {
                "date": str(today),
                "total": total,
                "published": published,
                "fallback": fallback_count,
                "failed": failed,
                "pending": pending,
            }

    return run_async(_digest())


@celery_app.task(bind=True)
def pipeline_health_check(self):
    """
    Daily health check: verify slots were created and content generated.
    Runs at 02:00 UTC (06:00 Dubai) to catch failures from the overnight pipeline.
    Auto-recovers by creating missing slots and triggering content generation.
    """
    logger.info("Running pipeline health check")

    async def _check():
        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            today = datetime.now(DUBAI_TZ).date()
            result = await db.execute(
                select(ContentSlot).where(
                    ContentSlot.scheduled_date == today
                )
            )
            slots = result.scalars().all()

            if not slots:
                # Auto-recover: create today's slots instead of just alerting
                logger.warning(f"No slots found for {today} — auto-creating now")
                try:
                    manager = SlotManager(db)
                    new_slots = await manager.create_daily_slots(today)
                    await db.commit()
                    logger.info(f"Auto-created {len(new_slots)} slots for {today}")
                    # Trigger content generation for the newly created slots
                    generate_all_pending_content.apply_async(countdown=10)
                    send_alert(
                        "Slots Auto-Recovered",
                        details={"Date": str(today), "Slots created": len(new_slots)},
                        error="Daily slot creation was missed — auto-recovered and triggered content generation",
                    )
                    return {"status": "auto_recovered", "slots_created": len(new_slots)}
                except Exception as e:
                    logger.error(f"Auto-recovery failed: {e}")
                    send_alert(
                        "No Slots Created — Auto-Recovery Failed",
                        details={"Date": str(today), "Error": str(e)[:200]},
                        error="Daily slot creation failed and auto-recovery also failed",
                    )
                    return {"status": "alert_sent", "issue": "no_slots_recovery_failed"}

            failed = [s for s in slots if s.status == "failed"]
            pending = [s for s in slots if s.status == "pending"]
            generating = [s for s in slots if s.status == "generating"]

            issues = []
            if failed:
                issues.append(f"{len(failed)} failed")
            if pending:
                issues.append(f"{len(pending)} still pending")
            if generating:
                issues.append(f"{len(generating)} stuck in generating")

            # Auto-recover stuck "generating" slots (likely from worker crash)
            if generating:
                for slot in generating:
                    logger.warning(f"Resetting stuck generating slot {slot.id} to pending")
                    slot.status = "pending"
                await db.commit()
                # Re-trigger content generation for reset slots
                generate_all_pending_content.apply_async(countdown=10)

            # Auto-recover pending slots (content generation was missed)
            if pending:
                logger.warning(f"Re-triggering content generation for {len(pending)} pending slots")
                generate_all_pending_content.apply_async(countdown=10)

            if issues:
                send_alert(
                    "Pipeline Health Issue",
                    details={
                        "Date": str(today),
                        "Total slots": len(slots),
                        "Issues": ", ".join(issues),
                        "Auto-recovery": "triggered" if (generating or pending) else "not needed",
                        "Failed slots": ", ".join(
                            f"#{s.slot_number}" for s in failed
                        ) or "none",
                    },
                    error="Content pipeline did not complete successfully",
                )
                return {"status": "alert_sent", "issues": issues, "auto_recovery": bool(generating or pending)}

            logger.info(f"Health check passed: {len(slots)} slots OK for {today}")
            return {"status": "ok", "slots": len(slots)}

    return run_async(_check())
