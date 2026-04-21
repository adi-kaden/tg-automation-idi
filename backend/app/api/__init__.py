# API routes
from fastapi import APIRouter

from app.api import auth, users, dashboard, scraper, content, published_posts, prompts, health

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(scraper.router, prefix="/scraper", tags=["Scraper"])
api_router.include_router(content.router, prefix="/content", tags=["Content"])
api_router.include_router(published_posts.router, prefix="/published-posts", tags=["Published Posts"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["Prompts"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
