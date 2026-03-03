"""
Scraper service module.
"""
from app.services.scraper.base import BaseScraper, ScrapedItem
from app.services.scraper.rss_scraper import RSSScraper
from app.services.scraper.website_scraper import WebsiteScraper
from app.services.scraper.rate_limiter import RateLimiter
from app.services.scraper.relevance_scorer import (
    calculate_relevance_score,
    calculate_engagement_potential,
)

__all__ = [
    "BaseScraper",
    "ScrapedItem",
    "RSSScraper",
    "WebsiteScraper",
    "RateLimiter",
    "calculate_relevance_score",
    "calculate_engagement_potential",
]
