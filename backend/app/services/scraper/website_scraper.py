"""
Website article scraper implementation.
Uses BeautifulSoup and trafilatura for content extraction.
"""
from datetime import datetime
from typing import List, Optional, Dict
from urllib.parse import urlparse
import json
import logging

from bs4 import BeautifulSoup
import trafilatura

from app.models.scrape_source import ScrapeSource
from app.services.scraper.base import BaseScraper, ScrapedItem
from app.services.scraper.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class WebsiteScraper(BaseScraper):
    """
    Scraper for website articles using CSS selectors.
    Falls back to trafilatura for content extraction.
    """

    def __init__(self, source: ScrapeSource, rate_limiter: RateLimiter | None = None):
        super().__init__(source, rate_limiter)
        self.selectors = self._parse_selectors()

    def _parse_selectors(self) -> Dict[str, str]:
        """Parse CSS selectors from source configuration."""
        if not self.source.css_selectors:
            return {}

        try:
            return json.loads(self.source.css_selectors)
        except json.JSONDecodeError:
            logger.warning(f"Invalid CSS selectors JSON for {self.source.name}")
            return {}

    async def scrape(self) -> List[ScrapedItem]:
        """
        Scrape website for articles.

        1. Fetch listing page
        2. Extract article links using CSS selectors or auto-detection
        3. Fetch each article page for full content
        """
        try:
            html = await self.fetch(self.source.url)
            article_urls = self._extract_article_urls(html)

            if not article_urls:
                logger.warning(f"No article URLs found for {self.source.name}")
                return []

            # Limit to reasonable number per scrape
            article_urls = article_urls[:20]

            items = []
            for url in article_urls:
                try:
                    item = await self._scrape_article(url)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.warning(f"Failed to scrape article {url}: {e}")
                    continue

            logger.info(
                f"Scraped {len(items)} articles from website: {self.source.name}"
            )
            return items

        except Exception as e:
            logger.error(f"Website scrape error for {self.source.name}: {e}")
            raise

    def _extract_article_urls(self, html: str) -> List[str]:
        """Extract article URLs from listing page."""
        soup = BeautifulSoup(html, "html.parser")
        urls = []

        # Use configured selector if available
        if "article_list" in self.selectors:
            elements = soup.select(self.selectors["article_list"])
            for el in elements:
                # Find link within element or check if element is a link
                link = el if el.name == "a" else el.find("a")
                if link and link.get("href"):
                    url = self.normalize_url(link["href"])
                    if self._is_article_url(url):
                        urls.append(url)
        else:
            # Auto-detect article links
            for link in soup.find_all("a", href=True):
                url = self.normalize_url(link["href"])
                if self._is_article_url(url):
                    urls.append(url)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _is_article_url(self, url: str) -> bool:
        """Check if URL looks like an article URL."""
        if not url:
            return False

        # Skip common non-article patterns
        skip_patterns = [
            "/category/",
            "/tag/",
            "/author/",
            "/page/",
            "/search",
            "/login",
            "/register",
            "/contact",
            "/about",
            "/privacy",
            "/terms",
            ".pdf",
            ".jpg",
            ".png",
            ".gif",
            "#",
            "mailto:",
            "javascript:",
            "/feed",
            "/rss",
        ]
        url_lower = url.lower()

        for pattern in skip_patterns:
            if pattern in url_lower:
                return False

        # Should be from same domain
        source_domain = urlparse(self.source.url).netloc
        url_domain = urlparse(url).netloc

        if not url_domain:
            return False

        return source_domain in url_domain or url_domain in source_domain

    async def _scrape_article(self, url: str) -> Optional[ScrapedItem]:
        """Scrape a single article page."""
        html = await self.fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = self._extract_title(soup)
        if not title:
            return None

        # Extract content using trafilatura
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_precision=True,
        )

        full_text = extracted if extracted else self._extract_body(soup)
        summary = full_text[:500] if full_text else None

        # Extract other metadata
        image_url = self._extract_image(soup)
        author = self._extract_author(soup)
        published_at = self._extract_date(soup)

        return ScrapedItem(
            url=url,
            title=title,
            summary=summary,
            full_text=full_text,
            image_url=image_url,
            author=author,
            published_at=published_at,
        )

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article title."""
        if "title" in self.selectors:
            el = soup.select_one(self.selectors["title"])
            if el:
                return el.get_text(strip=True)

        # Try common patterns
        for selector in ["h1.title", "h1.headline", "article h1", ".post-title", "h1"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if len(text) > 10:  # Skip too short titles
                    return text

        # Fallback to <title> tag
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            # Often contains site name, take first part
            return text.split("|")[0].split("-")[0].strip()

        return None

    def _extract_body(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article body text."""
        if "body" in self.selectors:
            el = soup.select_one(self.selectors["body"])
            if el:
                return el.get_text(separator=" ", strip=True)

        # Try common patterns
        for selector in [
            "article",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".article-body",
            "main",
        ]:
            el = soup.select_one(selector)
            if el:
                # Remove unwanted elements
                for tag in el.find_all(["script", "style", "nav", "aside", "footer"]):
                    tag.decompose()
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    return text

        return None

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main article image."""
        if "image" in self.selectors:
            el = soup.select_one(self.selectors["image"])
            if el:
                src = el.get("src") or el.get("data-src")
                if src:
                    return self.normalize_url(src)

        # Check Open Graph image
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return self.normalize_url(og_image["content"])

        # Check Twitter card image
        twitter_image = soup.find("meta", {"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            return self.normalize_url(twitter_image["content"])

        # Find first large image in article
        article = soup.find("article") or soup.find("main") or soup
        for img in article.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and not any(
                x in src.lower() for x in ["icon", "logo", "avatar", "button", "pixel"]
            ):
                return self.normalize_url(src)

        return None

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article author."""
        # Check meta tags
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta and author_meta.get("content"):
            return author_meta["content"]

        # Check common patterns
        for selector in [
            ".author",
            ".byline",
            "[rel='author']",
            ".author-name",
            ".post-author",
        ]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                # Clean up common prefixes
                for prefix in ["By ", "by ", "Written by ", "Author: "]:
                    if text.startswith(prefix):
                        text = text[len(prefix) :]
                if text and len(text) < 100:
                    return text

        return None

    def _extract_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract article publication date."""
        # Check meta tags
        for attr in ["article:published_time", "datePublished", "date"]:
            meta = soup.find("meta", property=attr) or soup.find("meta", {"name": attr})
            if meta and meta.get("content"):
                parsed = self._parse_date_string(meta["content"])
                if parsed:
                    return parsed

        # Check time elements
        time_el = soup.find("time")
        if time_el:
            datetime_attr = time_el.get("datetime")
            if datetime_attr:
                parsed = self._parse_date_string(datetime_attr)
                if parsed:
                    return parsed

        # Check configured selector
        if "date" in self.selectors:
            el = soup.select_one(self.selectors["date"])
            if el:
                parsed = self._parse_date_string(el.get_text(strip=True))
                if parsed:
                    return parsed

        return None

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None

        try:
            from dateutil import parser

            return parser.parse(date_str)
        except (ValueError, TypeError):
            return None
