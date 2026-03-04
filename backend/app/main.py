from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import api_router

settings = get_settings()


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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/debug/celery")
async def debug_celery():
    """Debug endpoint to check Celery/Redis connectivity."""
    import redis
    from app.tasks.celery_app import celery_app

    result = {
        "redis_url_configured": bool(settings.redis_url),
        "redis_url_prefix": settings.redis_url[:20] + "..." if settings.redis_url else None,
    }

    # Test Redis connection
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        result["redis_connected"] = True
    except Exception as e:
        result["redis_connected"] = False
        result["redis_error"] = str(e)

    # Check Celery worker status
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        result["celery_workers_active"] = active is not None and len(active) > 0
        result["celery_workers"] = list(active.keys()) if active else []
    except Exception as e:
        result["celery_workers_active"] = False
        result["celery_error"] = str(e)

    return result
