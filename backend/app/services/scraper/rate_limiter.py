"""
Rate limiter for scraping requests.
Uses asyncio.sleep for delays between requests to the same domain.
"""
import asyncio
from datetime import datetime
from typing import Dict

from app.config import get_settings


class RateLimiter:
    """
    Simple rate limiter that tracks last request time per domain.
    Ensures minimum delay between requests to the same domain.
    """

    def __init__(self, delay_seconds: float | None = None):
        settings = get_settings()
        self.delay_seconds = delay_seconds or settings.scrape_request_delay_sec
        self._last_request: Dict[str, datetime] = {}

    async def wait(self, domain: str) -> None:
        """
        Wait if needed before making a request to the given domain.

        Args:
            domain: The domain to rate limit (e.g., "gulfnews.com")
        """
        if domain in self._last_request:
            elapsed = (datetime.now() - self._last_request[domain]).total_seconds()
            if elapsed < self.delay_seconds:
                await asyncio.sleep(self.delay_seconds - elapsed)

        self._last_request[domain] = datetime.now()

    def reset(self, domain: str | None = None) -> None:
        """
        Reset rate limiter state.

        Args:
            domain: Specific domain to reset, or None to reset all
        """
        if domain:
            self._last_request.pop(domain, None)
        else:
            self._last_request.clear()
