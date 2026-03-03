"""
Abstract base class for all scrapers.
Defines common interface and shared functionality.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from urllib.parse import urlparse
import logging

import httpx

from app.config import get_settings
from app.models.scrape_source import ScrapeSource
from app.services.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


@dataclass
class ScrapedItem:
    """Data class for a scraped article."""
    url: str
    title: str
    summary: Optional[str] = None
    full_text: Optional[str] = None
    image_url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None


class BaseScraper(ABC):
    """
    Abstract base class for scrapers.

    Provides:
    - HTTP client with proper headers
    - Rate limiting
    - Error handling
    - Common extraction utilities
    """

    def __init__(self, source: ScrapeSource, rate_limiter: RateLimiter | None = None):
        self.source = source
        self.rate_limiter = rate_limiter or RateLimiter()
        self._client: Optional[httpx.AsyncClient] = None
        self._settings = get_settings()

    @property
    def domain(self) -> str:
        """Extract domain from source URL."""
        return urlparse(self.source.url).netloc

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper headers."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": self._settings.scrape_user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch(self, url: str) -> str:
        """
        Fetch URL content with rate limiting.

        Args:
            url: URL to fetch

        Returns:
            Response text content

        Raises:
            httpx.HTTPError: On request failure
        """
        # Apply rate limiting
        await self.rate_limiter.wait(self.domain)

        client = await self.get_client()
        response = await client.get(url)
        response.raise_for_status()

        return response.text

    @abstractmethod
    async def scrape(self) -> List[ScrapedItem]:
        """
        Scrape the source and return list of items.
        Must be implemented by subclasses.

        Returns:
            List of scraped items
        """
        pass

    def normalize_url(self, url: str) -> str:
        """
        Normalize URL to absolute form.

        Args:
            url: URL that may be relative or protocol-relative

        Returns:
            Absolute URL
        """
        if not url:
            return ""

        # Protocol-relative URL
        if url.startswith("//"):
            return f"https:{url}"

        # Relative URL
        if url.startswith("/"):
            parsed = urlparse(self.source.url)
            return f"{parsed.scheme}://{parsed.netloc}{url}"

        # Missing protocol
        if not url.startswith(("http://", "https://")):
            return f"https://{url}"

        return url
