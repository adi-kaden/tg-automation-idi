from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.api import api_router
from app.database import AsyncSessionLocal
from app.models.user import User
from app.utils.security import hash_password

settings = get_settings()


async def seed_admin_user():
    """Create admin user if it doesn't exist."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == "admin@idigov.com")
        )
        existing = result.scalar_one_or_none()
        if existing:
            print("Admin user already exists")
            return
        admin = User(
            email="admin@idigov.com",
            hashed_password=hash_password("Admin123!"),
            full_name="Admin User",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print("Admin user created: admin@idigov.com / Admin123!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("TG Content Engine API starting up...")
    await seed_admin_user()
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
