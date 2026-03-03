# API routes
from fastapi import APIRouter

from app.api import auth, users, dashboard, scraper, content

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(scraper.router, prefix="/scraper", tags=["Scraper"])
api_router.include_router(content.router, prefix="/content", tags=["Content"])
