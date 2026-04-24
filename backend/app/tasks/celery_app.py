"""
Celery application configuration.
"""
import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure, worker_ready

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "tg_content_engine",
    broker=settings.effective_redis_url,
    backend=settings.effective_redis_url,
    include=[
        "app.tasks.scraper_tasks",
        "app.tasks.content_tasks",
        "app.tasks.analytics_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max per task
    task_soft_time_limit=1500,  # Soft limit 25 minutes
    worker_prefetch_multiplier=1,  # Process one task at a time
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Requeue if worker dies
)

# Beat schedule for periodic tasks
# Times are in UTC, Dubai is GMT+4
celery_app.conf.beat_schedule = {
    # ==================== Daily Content Pipeline ====================

    # 04:00 Dubai = 00:00 UTC - Scrape all sources
    "scrape-all-sources-daily": {
        "task": "app.tasks.scraper_tasks.scrape_all_sources",
        "schedule": crontab(hour=0, minute=0),
        "kwargs": {"run_type": "scheduled"},
    },

    # 05:00 Dubai = 01:00 UTC - Create daily slots
    "create-daily-slots": {
        "task": "app.tasks.content_tasks.create_daily_slots_task",
        "schedule": crontab(hour=1, minute=0),
    },

    # 05:30 Dubai = 01:30 UTC - Generate content for all pending slots
    "generate-pending-content": {
        "task": "app.tasks.content_tasks.generate_all_pending_content",
        "schedule": crontab(hour=1, minute=30),
    },

    # ==================== Auto-Selection (30 min before each slot) ====================

    # Check every 5 minutes for slots needing auto-selection
    "check-auto-select": {
        "task": "app.tasks.content_tasks.check_and_auto_select",
        "schedule": crontab(minute="*/5"),
    },

    # ==================== Publishing Schedule ====================
    # Slot times in Dubai: 08:00, 12:00, 16:00, 20:00, 00:00
    # In UTC: 04:00, 08:00, 12:00, 16:00, 20:00
    # Each task passes slot_number to identify exactly which slot to publish

    # Slot 1: 08:00 Dubai = 04:00 UTC
    "publish-slot-1": {
        "task": "app.tasks.content_tasks.publish_scheduled_slot",
        "schedule": crontab(hour=4, minute=0),
        "kwargs": {"slot_number": 1},
    },

    # Slot 2: 12:00 Dubai = 08:00 UTC
    "publish-slot-2": {
        "task": "app.tasks.content_tasks.publish_scheduled_slot",
        "schedule": crontab(hour=8, minute=0),
        "kwargs": {"slot_number": 2},
    },

    # Slot 3: 16:00 Dubai = 12:00 UTC
    "publish-slot-3": {
        "task": "app.tasks.content_tasks.publish_scheduled_slot",
        "schedule": crontab(hour=12, minute=0),
        "kwargs": {"slot_number": 3},
    },

    # Slot 4: 20:00 Dubai = 16:00 UTC
    "publish-slot-4": {
        "task": "app.tasks.content_tasks.publish_scheduled_slot",
        "schedule": crontab(hour=16, minute=0),
        "kwargs": {"slot_number": 4},
    },

    # Slot 5: 00:00 Dubai = 20:00 UTC
    "publish-slot-5": {
        "task": "app.tasks.content_tasks.publish_scheduled_slot",
        "schedule": crontab(hour=20, minute=0),
        "kwargs": {"slot_number": 5},
    },

    # ==================== Catch-up: Publish Overdue Slots ====================

    # Every 10 minutes (offset by 3 min to avoid racing with scheduled publishes at :00)
    "publish-overdue-slots": {
        "task": "app.tasks.content_tasks.publish_overdue_slots",
        "schedule": crontab(minute="3,13,23,33,43,53"),
    },

    # ==================== Watchdog: Never Miss a Slot ====================

    # Every minute: checks slots scheduled in the last 15 min that haven't
    # published, applies recovery ladder (retry publish → force auto-select
    # → evergreen fallback). Also writes a Redis heartbeat for external checks.
    "watchdog-check-slots": {
        "task": "app.tasks.content_tasks.watchdog_check_slots",
        "schedule": crontab(minute="*"),
    },

    # ==================== Article Cleanup ====================

    # 03:00 Dubai = 23:00 UTC - Delete all articles older than 2 days
    "cleanup-old-articles": {
        "task": "app.tasks.scraper_tasks.cleanup_old_articles",
        "schedule": crontab(hour=23, minute=0),
        "kwargs": {"days_old": 2},
    },

    # ==================== Pipeline Health Check ====================

    # 02:00 UTC = 06:00 Dubai - Check if overnight pipeline succeeded
    "pipeline-health-check": {
        "task": "app.tasks.content_tasks.pipeline_health_check",
        "schedule": crontab(hour=2, minute=0),
    },

    # Every 2 hours - Lightweight check to catch missed slots during the day
    "ensure-pipeline-running": {
        "task": "app.tasks.content_tasks.ensure_todays_pipeline",
        "schedule": crontab(minute=15, hour="*/2"),
    },

    # 23:55 Dubai = 19:55 UTC - Daily digest to admin alert chat so ops knows
    # the system is alive even on all-green days and sees partial failures.
    "send-daily-digest": {
        "task": "app.tasks.content_tasks.send_daily_digest",
        "schedule": crontab(hour=19, minute=55),
    },

    # ==================== Analytics Collection ====================

    # Collect post analytics every 5 minutes (last 7 days of posts)
    "collect-post-analytics": {
        "task": "app.tasks.analytics_tasks.collect_post_analytics",
        "schedule": crontab(minute="*/5"),
        "kwargs": {"days_back": 7},
    },

    # Create daily channel snapshot at 23:00 Dubai = 19:00 UTC
    "daily-channel-snapshot": {
        "task": "app.tasks.analytics_tasks.create_daily_channel_snapshot",
        "schedule": crontab(hour=19, minute=0),
    },
}


# ==================== Worker Startup: Ensure Today's Slots Exist ====================

@worker_ready.connect
def ensure_todays_slots_on_startup(sender=None, **kwargs):
    """
    When the Celery worker starts, check if today's slots exist.
    If not, create them and trigger content generation.
    This catches missed slot creation from worker/beat downtime.
    """
    logger.info("Worker ready — checking if today's slots exist")
    # Delay 15s to let the worker fully initialize before running tasks
    celery_app.send_task(
        "app.tasks.content_tasks.ensure_todays_pipeline",
        countdown=15,
    )


# ==================== Global Task Failure Notifications ====================

_TASK_DISPLAY_NAMES = {
    "app.tasks.content_tasks.create_daily_slots_task": "Create Daily Slots",
    "app.tasks.content_tasks.generate_content_for_slot": "Generate Content",
    "app.tasks.content_tasks.generate_all_pending_content": "Generate All Content",
    "app.tasks.content_tasks.auto_select_for_slot": "Auto-Select Option",
    "app.tasks.content_tasks.check_and_auto_select": "Check Auto-Select",
    "app.tasks.content_tasks.publish_scheduled_slot": "Publish to Telegram",
    "app.tasks.content_tasks.publish_overdue_slots": "Publish Overdue Slots",
    "app.tasks.scraper_tasks.scrape_all_sources": "Scrape All Sources",
    "app.tasks.scraper_tasks.scrape_single_source": "Scrape Single Source",
    "app.tasks.scraper_tasks.cleanup_old_articles": "Cleanup Articles",
    "app.tasks.content_tasks.pipeline_health_check": "Pipeline Health Check",
    "app.tasks.content_tasks.ensure_todays_pipeline": "Ensure Today's Pipeline",
    "app.tasks.content_tasks.watchdog_check_slots": "Slot Watchdog",
    "app.tasks.content_tasks.send_daily_digest": "Daily Digest",
    "app.tasks.analytics_tasks.collect_post_analytics": "Collect Analytics",
    "app.tasks.analytics_tasks.create_daily_channel_snapshot": "Channel Snapshot",
}


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Cooldown (seconds) for deduping identical failure alerts. A single
# Postgres recovery can otherwise produce a dozen identical alerts in
# under a minute as every scheduled task hits the same error.
_FAILURE_ALERT_COOLDOWN = 600


def _should_send_failure_alert(task_name: str, error_str: str) -> tuple[bool, int]:
    """
    Return (send?, suppressed_count). Uses Redis SET NX EX to collapse
    repeated identical alerts (same task + same error signature) into one
    alert per cooldown window. On Redis failure we always send.
    """
    import hashlib
    try:
        import redis as redis_lib
        normalized = f"{task_name}|{error_str[:160]}"
        sig = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:16]
        client = redis_lib.from_url(settings.effective_redis_url, socket_timeout=3)
        key = f"tfail:dedupe:{sig}"
        was_first = client.set(key, "1", nx=True, ex=_FAILURE_ALERT_COOLDOWN)
        if was_first:
            return True, 0
        # Already sent recently — bump a counter so we know how many were suppressed.
        count_key = f"tfail:dedupe:count:{sig}"
        suppressed = client.incr(count_key)
        client.expire(count_key, _FAILURE_ALERT_COOLDOWN)
        logger.info(
            f"Suppressing duplicate failure alert: {task_name} "
            f"(sig={sig}, suppressed_so_far={suppressed})"
        )
        return False, suppressed
    except Exception as exc:
        logger.warning(f"Failure-alert dedupe check failed, sending anyway: {exc}")
        return True, 0


@task_failure.connect
def notify_task_failure(sender=None, task_id=None, exception=None,
                        args=None, kwargs=None, traceback=None,
                        einfo=None, **kw):
    """
    Send Telegram notification when ANY Celery task permanently fails.

    This fires after all retries are exhausted, so it only notifies on
    genuine permanent failures — not transient retry-able errors.
    Sends to both the SMM chat and the admin alert chat independently.

    Identical failures (same task + same error) within a short cooldown
    are deduped so a Postgres recovery window can't spam the channel.
    """
    bot_token = settings.telegram_bot_token
    if not bot_token:
        return

    task_name = getattr(sender, "name", None) or "Unknown"
    display_name = _TASK_DISPLAY_NAMES.get(task_name, task_name.rsplit(".", 1)[-1])

    raw_error = str(exception)[:300] if exception else "Unknown error"
    error_str = _escape_html(raw_error)

    should_send, suppressed = _should_send_failure_alert(task_name, raw_error)
    if not should_send:
        return

    # Build context from args/kwargs
    ctx_parts = []
    if kwargs:
        for k, v in kwargs.items():
            ctx_parts.append(f"{k}={v}")
    if args:
        ctx_parts.extend(str(a)[:80] for a in args)
    context = _escape_html(", ".join(ctx_parts)) if ctx_parts else "—"

    from datetime import datetime
    from zoneinfo import ZoneInfo
    now_str = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%H:%M %d/%m/%Y")

    message = (
        f"🚨 <b>Task Failed</b>\n\n"
        f"📋 <b>Task:</b> {display_name}\n"
        f"❌ <b>Error:</b> {error_str}\n"
        f"📝 <b>Context:</b> {context}\n"
        f"🕐 <b>Time:</b> {now_str} Dubai"
    )

    import httpx
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # Send to each chat independently — one failure doesn't block the other
    chat_ids = set()
    if settings.telegram_smm_chat_id:
        chat_ids.add(settings.telegram_smm_chat_id)
    if settings.telegram_alert_chat_id:
        chat_ids.add(settings.telegram_alert_chat_id)

    for cid in chat_ids:
        try:
            httpx.post(url, json={
                "chat_id": cid,
                "text": message,
                "parse_mode": "HTML",
            }, timeout=10)
        except Exception as exc:
            logger.error(f"Failed to send task failure notification to {cid}: {exc}")
