"""
Celery tasks for analytics collection.
"""
import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.services.analytics_collector import AnalyticsCollector
from app.tasks.celery_app import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)


def get_async_session():
    """Create a fresh async session for each task."""
    engine = create_async_engine(settings.database_url, pool_size=3, pool_pre_ping=True)
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
def collect_post_analytics(self, hours_back: int = 48):
    """
    Collect analytics for recently published posts.

    Args:
        hours_back: How far back to look for posts to update
    """
    logger.info(f"Collecting post analytics for last {hours_back} hours")

    async def _collect():
        try:
            collector = AnalyticsCollector()
        except ValueError as e:
            logger.error(f"Analytics collector not configured: {e}")
            return {"error": str(e)}

        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            result = await collector.collect_all_post_analytics(db, hours_back=hours_back)
            return result

    try:
        return run_async(_collect())
    except Exception as e:
        logger.error(f"Failed to collect post analytics: {e}")
        self.retry(countdown=300, exc=e)


@celery_app.task(bind=True, max_retries=2)
def create_daily_channel_snapshot(self, snapshot_date_str: str = None):
    """
    Create daily channel snapshot.

    Args:
        snapshot_date_str: Date string (YYYY-MM-DD) or None for today
    """
    if snapshot_date_str:
        snapshot_date = date.fromisoformat(snapshot_date_str)
    else:
        snapshot_date = date.today()

    logger.info(f"Creating channel snapshot for {snapshot_date}")

    async def _create_snapshot():
        try:
            collector = AnalyticsCollector()
        except ValueError as e:
            logger.error(f"Analytics collector not configured: {e}")
            return {"error": str(e)}

        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            result = await collector.create_daily_snapshot(db, snapshot_date=snapshot_date)
            return result

    try:
        return run_async(_create_snapshot())
    except Exception as e:
        logger.error(f"Failed to create daily snapshot: {e}")
        self.retry(countdown=300, exc=e)


@celery_app.task(bind=True)
def backfill_snapshots(self, days: int = 7):
    """
    Backfill missing channel snapshots for the past N days.

    Args:
        days: Number of days to backfill
    """
    logger.info(f"Backfilling channel snapshots for last {days} days")

    results = []
    for i in range(days):
        snapshot_date = date.today() - timedelta(days=i)
        task = create_daily_channel_snapshot.delay(snapshot_date.isoformat())
        results.append({
            "date": snapshot_date.isoformat(),
            "task_id": task.id,
        })

    return {
        "days_queued": len(results),
        "tasks": results,
    }


@celery_app.task(bind=True)
def get_analytics_summary(self, days: int = 7):
    """
    Get analytics summary for dashboard.

    Args:
        days: Number of days to include in summary
    """
    logger.info(f"Getting analytics summary for last {days} days")

    async def _get_summary():
        try:
            collector = AnalyticsCollector()
        except ValueError as e:
            logger.error(f"Analytics collector not configured: {e}")
            return {"error": str(e)}

        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            result = await collector.get_analytics_summary(db, days=days)
            return result

    return run_async(_get_summary())
