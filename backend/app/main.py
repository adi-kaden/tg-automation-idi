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
async def health_check(debug: bool = False):
    """Health check endpoint with optional debug info."""
    result = {"status": "healthy"}

    if debug:
        import redis
        from app.tasks.celery_app import celery_app

        result["redis_url_set"] = bool(settings.redis_url and settings.redis_url != "redis://localhost:6379/0")
        result["redis_url_prefix"] = settings.redis_url[:30] + "..." if settings.redis_url else None

        # Test Redis
        try:
            r = redis.from_url(settings.redis_url)
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


