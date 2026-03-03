"""
RSS feed scraper implementation.
Uses feedparser for RSS/Atom feed parsing.
"""
from datetime import datetime, timezone
from typing import List, Optional
import logging

import feedparser
from bs4 import BeautifulSoup

from app.models.scrape_source import ScrapeSource
from app.services.scraper.base import BaseScraper, ScrapedItem
from app.services.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class RSSScraper(BaseScraper):
    """
    Scraper for RSS and Atom feeds.
    """

    def __init__(self, source: ScrapeSource, rate_limiter: RateLimiter | None = None):
        super().__init__(source, rate_limiter)

    async def scrape(self) -> List[ScrapedItem]:
        """
        Parse RSS feed and extract articles.

        Returns:
            List of scraped items from the feed
        """
        try:
            content = await self.fetch(self.source.url)
            feed = feedparser.parse(content)

            if feed.bozo and not feed.entries:
                logger.warning(
                    f"RSS feed parse error for {self.source.name}: {feed.bozo_exception}"
                )
                return []

            items = []
            for entry in feed.entries:
                item = self._parse_entry(entry)
                if item:
                    items.append(item)

            logger.info(f"Scraped {len(items)} items from RSS feed: {self.source.name}")
            return items

        except Exception as e:
            logger.error(f"RSS scrape error for {self.source.name}: {e}")
            raise

    def _parse_entry(self, entry: dict) -> Optional[ScrapedItem]:
        """Parse a single feed entry into a ScrapedItem."""
        url = entry.get("link", "")
        title = entry.get("title", "")

        if not url or not title:
            return None

        # Extract summary (strip HTML tags)
        summary = entry.get("summary", "") or entry.get("description", "")
        if summary:
            soup = BeautifulSoup(summary, "html.parser")
            summary = soup.get_text(strip=True)[:500]

        # Extract image from media content or enclosures
        image_url = self._extract_image(entry)

        # Parse published date
        published_at = self._parse_date(entry)

        # Extract author
        author = entry.get("author", "") or entry.get("dc_creator", "")

        return ScrapedItem(
            url=self.normalize_url(url),
            title=title.strip(),
            summary=summary or None,
            image_url=image_url,
            author=author or None,
            published_at=published_at,
        )

    def _extract_image(self, entry: dict) -> Optional[str]:
        """Extract image URL from feed entry."""
        # Check media:content
        media = entry.get("media_content", [])
        if media:
            for m in media:
                if m.get("type", "").startswith("image") or m.get("medium") == "image":
                    url = m.get("url", "")
                    if url:
                        return self.normalize_url(url)

        # Check media:thumbnail
        thumbnail = entry.get("media_thumbnail", [])
        if thumbnail:
            url = thumbnail[0].get("url", "")
            if url:
                return self.normalize_url(url)

        # Check enclosures
        enclosures = entry.get("enclosures", [])
        for enc in enclosures:
            if enc.get("type", "").startswith("image"):
                url = enc.get("href", "") or enc.get("url", "")
                if url:
                    return self.normalize_url(url)

        # Try to extract from content/summary HTML
        content = entry.get("content", [{}])
        content_value = content[0].get("value", "") if content else ""
        html_content = content_value or entry.get("summary", "")

        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            img = soup.find("img")
            if img and img.get("src"):
                return self.normalize_url(img["src"])

        return None

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """Parse published date from entry."""
        # feedparser often provides parsed time tuple
        time_tuple = entry.get("published_parsed") or entry.get("updated_parsed")

        if time_tuple:
            try:
                return datetime(
                    time_tuple[0],
                    time_tuple[1],
                    time_tuple[2],
                    time_tuple[3],
                    time_tuple[4],
                    time_tuple[5],
                    tzinfo=timezone.utc,
                )
            except (ValueError, TypeError):
                pass

        # Try to parse string date
        date_str = entry.get("published", "") or entry.get("updated", "")
        if date_str:
            try:
                from email.utils import parsedate_to_datetime

                return parsedate_to_datetime(date_str)
            except (ValueError, TypeError):
                pass

            # Try dateutil as fallback
            try:
                from dateutil import parser

                return parser.parse(date_str)
            except (ValueError, TypeError):
                pass

        return None
