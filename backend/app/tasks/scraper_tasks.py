"""
Celery tasks for scraping operations.
"""
import asyncio
from datetime import datetime
from uuid import UUID
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.scrape_source import ScrapeSource
from app.models.scrape_run import ScrapeRun
from app.models.scraped_article import ScrapedArticle
from app.services.scraper import (
    RSSScraper,
    WebsiteScraper,
    RateLimiter,
    ScrapedItem,
    calculate_relevance_score,
    calculate_engagement_potential,
)
from app.tasks.celery_app import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)

# Create separate engine for Celery tasks (runs in sync context)
engine = create_async_engine(settings.async_database_url, pool_size=3)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3)
def scrape_all_sources(self, run_type: str = "scheduled"):
    """
    Scrape all active sources.

    Args:
        run_type: "scheduled", "manual", or "retry"

    Returns:
        Dict with sources_processed and articles_new counts
    """
    logger.info(f"Starting scrape_all_sources task (run_type={run_type})")

    async def _scrape_all():
        async with AsyncSessionLocal() as db:
            # Get all active sources
            result = await db.execute(
                select(ScrapeSource).where(ScrapeSource.is_active == True)
            )
            sources = result.scalars().all()

            if not sources:
                logger.warning("No active sources found")
                return {"sources_processed": 0, "articles_new": 0}

            rate_limiter = RateLimiter()
            total_new = 0
            sources_processed = 0

            for source in sources:
                try:
                    new_count = await _scrape_source(db, source, rate_limiter, run_type)
                    total_new += new_count
                    sources_processed += 1
                except Exception as e:
                    logger.error(f"Failed to scrape source {source.name}: {e}")
                    continue

            return {
                "sources_processed": sources_processed,
                "articles_new": total_new,
            }

    try:
        return run_async(_scrape_all())
    except Exception as e:
        logger.error(f"scrape_all_sources failed: {e}")
        self.retry(countdown=300, exc=e)  # Retry in 5 minutes


@celery_app.task(bind=True, max_retries=3)
def scrape_single_source(self, source_id: str, run_type: str = "manual"):
    """
    Scrape a single source.

    Args:
        source_id: UUID string of the source to scrape
        run_type: "scheduled", "manual", or "retry"

    Returns:
        Dict with source info and articles_new count
    """
    logger.info(f"Starting scrape_single_source task for {source_id}")

    async def _scrape_single():
        async with AsyncSessionLocal() as db:
            source_uuid = UUID(source_id)
            result = await db.execute(
                select(ScrapeSource).where(ScrapeSource.id == source_uuid)
            )
            source = result.scalar_one_or_none()

            if not source:
                logger.error(f"Source not found: {source_id}")
                return {"error": "Source not found"}

            rate_limiter = RateLimiter()
            new_count = await _scrape_source(db, source, rate_limiter, run_type)

            return {
                "source_id": source_id,
                "source_name": source.name,
                "articles_new": new_count,
            }

    try:
        return run_async(_scrape_single())
    except Exception as e:
        logger.error(f"scrape_single_source failed for {source_id}: {e}")
        self.retry(countdown=60, exc=e)


async def _scrape_source(
    db: AsyncSession,
    source: ScrapeSource,
    rate_limiter: RateLimiter,
    run_type: str,
) -> int:
    """
    Internal function to scrape a single source.

    Args:
        db: Database session
        source: ScrapeSource to scrape
        rate_limiter: Shared rate limiter
        run_type: Type of run (scheduled, manual, retry)

    Returns:
        Number of new articles saved
    """
    # Create scrape run record
    scrape_run = ScrapeRun(
        source_id=source.id,
        run_type=run_type,
        status="running",
    )
    db.add(scrape_run)
    await db.commit()
    await db.refresh(scrape_run)

    scraper = None
    try:
        # Select appropriate scraper based on source type
        if source.source_type == "rss":
            scraper = RSSScraper(source, rate_limiter)
        elif source.source_type == "website":
            scraper = WebsiteScraper(source, rate_limiter)
        else:
            raise ValueError(f"Unsupported source type: {source.source_type}")

        # Perform scraping
        items = await scraper.scrape()

        # Save articles (with deduplication)
        articles_found = len(items)
        articles_new = 0

        for item in items:
            saved = await _save_article(db, source, scrape_run, item)
            if saved:
                articles_new += 1

        # Update scrape run as completed
        scrape_run.status = "completed"
        scrape_run.articles_found = articles_found
        scrape_run.articles_new = articles_new
        scrape_run.completed_at = datetime.utcnow()

        # Update source last_scraped_at
        source.last_scraped_at = datetime.utcnow()
        source.last_error = None

        # Adjust reliability score (success increases it)
        source.reliability_score = min(1.0, source.reliability_score + 0.05)

        await db.commit()

        logger.info(f"Scraped {source.name}: {articles_found} found, {articles_new} new")
        return articles_new

    except Exception as e:
        # Update scrape run as failed
        scrape_run.status = "failed"
        scrape_run.error_message = str(e)[:500]
        scrape_run.completed_at = datetime.utcnow()

        # Update source with error
        source.last_error = str(e)[:500]

        # Decrease reliability score on failure
        source.reliability_score = max(0.0, source.reliability_score - 0.1)

        await db.commit()
        raise

    finally:
        # Always close the scraper
        if scraper:
            await scraper.close()


async def _save_article(
    db: AsyncSession,
    source: ScrapeSource,
    scrape_run: ScrapeRun,
    item: ScrapedItem,
) -> bool:
    """
    Save scraped article with deduplication.

    Args:
        db: Database session
        source: Source the article came from
        scrape_run: Current scrape run
        item: Scraped item to save

    Returns:
        True if article was saved (new), False if duplicate
    """
    # Check for existing article with same URL
    result = await db.execute(
        select(ScrapedArticle).where(ScrapedArticle.url == item.url)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return False  # Duplicate

    # Calculate scores
    relevance = calculate_relevance_score(item, source.category)
    engagement = calculate_engagement_potential(item)

    # Convert timezone-aware datetime to naive (UTC) for database storage
    published_at = item.published_at
    if published_at and published_at.tzinfo is not None:
        published_at = published_at.replace(tzinfo=None)

    # Create article
    article = ScrapedArticle(
        source_id=source.id,
        scrape_run_id=scrape_run.id,
        url=item.url,
        title=item.title,
        summary=item.summary,
        full_text=item.full_text,
        image_url=item.image_url,
        author=item.author,
        published_at=published_at,
        category=source.category,
        relevance_score=relevance,
        engagement_potential=engagement,
    )

    db.add(article)
    return True
