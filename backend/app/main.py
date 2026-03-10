from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import get_settings
from app.api import api_router

settings = get_settings()

# Image storage directory
IMAGES_DIR = Path("generated_images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("TG Content Engine API starting up...")
    yield
    # Shutdown
    print("TG Content Engine API shutting down...")


app = FastAPI(
    title="TG Content Engine API",
    description="Telegram content automation platform for IDIGOV Real Estate",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "TG Content Engine API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/images/{filename}")
async def serve_image(filename: str):
    """Serve generated images."""
    # Sanitize filename to prevent directory traversal
    safe_filename = Path(filename).name
    file_path = IMAGES_DIR / safe_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(
        file_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/health")
async def health_check(debug: bool = False):
    """Health check endpoint with optional debug info."""
    result = {"status": "healthy"}

    if debug:
        import redis
        from app.tasks.celery_app import celery_app

        redis_url = settings.effective_redis_url
        result["redis_url_set"] = bool(redis_url and redis_url != "redis://localhost:6379/0")
        result["redis_url_prefix"] = redis_url[:30] + "..." if redis_url else None

        # Test Redis
        try:
            r = redis.from_url(redis_url)
            r.ping()
            result["redis_ok"] = True
        except Exception as e:
            result["redis_ok"] = False
            result["redis_error"] = str(e)[:100]

        # Check Celery workers
        try:
            inspect = celery_app.control.inspect(timeout=2.0)
            active = inspect.active()
            result["celery_workers"] = list(active.keys()) if active else []
        except Exception as e:
            result["celery_workers"] = []
            result["celery_error"] = str(e)[:100]

    return result


@app.get("/debug/articles")
async def debug_articles():
    """
    Public debug endpoint to check article counts.
    No authentication required.
    """
    from sqlalchemy import select, func
    from app.database import AsyncSessionLocal
    from app.models.scraped_article import ScrapedArticle
    from app.models.scrape_source import ScrapeSource
    from app.models.scrape_run import ScrapeRun

    try:
        async with AsyncSessionLocal() as db:
            # Count all articles
            total_result = await db.execute(select(func.count(ScrapedArticle.id)))
            total = total_result.scalar()

            # Count unused articles
            unused_result = await db.execute(
                select(func.count(ScrapedArticle.id))
                .where(ScrapedArticle.used_in_post_id.is_(None))
            )
            unused = unused_result.scalar()

            # Count by category (unused only)
            category_result = await db.execute(
                select(ScrapedArticle.category, func.count(ScrapedArticle.id))
                .where(ScrapedArticle.used_in_post_id.is_(None))
                .group_by(ScrapedArticle.category)
            )
            by_category = {cat: count for cat, count in category_result.all()}

            # Count active sources
            sources_result = await db.execute(
                select(func.count(ScrapeSource.id)).where(ScrapeSource.is_active == True)
            )
            active_sources = sources_result.scalar()

            # Get last 3 scrape runs
            runs_result = await db.execute(
                select(ScrapeRun)
                .order_by(ScrapeRun.started_at.desc())
                .limit(3)
            )
            recent_runs = [
                {
                    "status": r.status,
                    "articles_found": r.articles_found,
                    "articles_new": r.articles_new,
                    "error": r.error_message[:80] if r.error_message else None,
                }
                for r in runs_result.scalars().all()
            ]

            return {
                "total_articles": total,
                "unused_articles": unused,
                "by_category": by_category,
                "active_sources": active_sources,
                "recent_runs": recent_runs,
                "can_generate": {
                    "real_estate": by_category.get("real_estate", 0) + by_category.get("construction", 0) > 0,
                    "general_dubai": sum(v for k, v in by_category.items() if k not in ["real_estate", "construction"]) > 0,
                },
            }
    except Exception as e:
        return {"error": str(e)}


@app.post("/debug/cleanup-old-articles")
async def debug_cleanup_old_articles(days_old: int = 2):
    """
    Delete articles older than `days_old` days by scraped_at OR published_at.
    Also prunes expired rejected URLs. No authentication required (debug endpoint).
    """
    from datetime import datetime, timedelta
    from sqlalchemy import select, func, delete as sql_delete, update as sql_update, or_, and_
    from app.database import AsyncSessionLocal
    from app.models.scraped_article import ScrapedArticle
    from app.models.rejected_url import RejectedArticleURL

    try:
        async with AsyncSessionLocal() as db:
            cutoff = datetime.utcnow() - timedelta(days=days_old)

            age_filter = or_(
                ScrapedArticle.scraped_at < cutoff,
                and_(
                    ScrapedArticle.published_at.is_not(None),
                    ScrapedArticle.published_at < cutoff,
                ),
            )

            # Count articles to be deleted
            count_result = await db.execute(
                select(func.count(ScrapedArticle.id)).where(age_filter)
            )
            to_delete = count_result.scalar()

            # Clear FK references first
            await db.execute(
                sql_update(ScrapedArticle)
                .where(ScrapedArticle.used_in_post_id.is_not(None), age_filter)
                .values(used_in_post_id=None)
            )

            # Delete old articles
            result = await db.execute(
                sql_delete(ScrapedArticle).where(age_filter)
            )
            deleted = result.rowcount

            # Prune expired rejected URLs
            result2 = await db.execute(
                sql_delete(RejectedArticleURL).where(
                    RejectedArticleURL.expires_at < datetime.utcnow()
                )
            )
            pruned_urls = result2.rowcount

            await db.commit()

            return {
                "deleted_articles": deleted,
                "pruned_rejected_urls": pruned_urls,
                "cutoff": str(cutoff),
                "message": f"Deleted {deleted} articles older than {days_old} days, pruned {pruned_urls} expired rejected URLs",
            }
    except Exception as e:
        return {"error": str(e)}


