"""
Pydantic schemas for scraper API.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ========== Source Schemas ==========


class ScrapeSourceBase(BaseModel):
    """Base schema for scrape source."""

    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., max_length=1000)
    source_type: str = Field(..., pattern="^(rss|website|api|data_portal)$")
    category: str = Field(
        ...,
        pattern="^(real_estate|economy|tech|construction|regulation|lifestyle|events|tourism|food_dining|sports|transportation|culture|entertainment|education|health|environment|government|business|general)$",
    )
    language: str = Field(default="en", pattern="^(en|ar|ru)$")
    scrape_frequency_hours: int = Field(default=6, ge=1, le=168)
    css_selectors: Optional[str] = None  # JSON string


class ScrapeSourceCreate(ScrapeSourceBase):
    """Schema for creating a scrape source."""

    pass


class ScrapeSourceUpdate(BaseModel):
    """Schema for updating a scrape source."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, max_length=1000)
    source_type: Optional[str] = Field(None, pattern="^(rss|website|api|data_portal)$")
    category: Optional[str] = None
    language: Optional[str] = Field(None, pattern="^(en|ar|ru)$")
    scrape_frequency_hours: Optional[int] = Field(None, ge=1, le=168)
    css_selectors: Optional[str] = None
    is_active: Optional[bool] = None


class ScrapeSourceResponse(ScrapeSourceBase):
    """Schema for scrape source response."""

    id: UUID
    is_active: bool
    last_scraped_at: Optional[datetime]
    last_error: Optional[str]
    reliability_score: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScrapeRunSummary(BaseModel):
    """Summary schema for scrape run."""

    id: UUID
    run_type: str
    status: str
    articles_found: int
    articles_new: int
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScrapeSourceDetail(ScrapeSourceResponse):
    """Detailed scrape source response with stats."""

    total_articles: int = 0
    recent_runs: List[ScrapeRunSummary] = []


# ========== Run Schemas ==========


class ScrapeRunResponse(ScrapeRunSummary):
    """Full schema for scrape run response."""

    source_id: Optional[UUID]
    source_name: Optional[str] = None
    error_message: Optional[str]

    class Config:
        from_attributes = True


class ScrapeRunTrigger(BaseModel):
    """Response for triggering a manual scrape."""

    task_id: str
    source_id: UUID
    message: str


# ========== Article Schemas ==========


class ScrapedArticleResponse(BaseModel):
    """Schema for scraped article response."""

    id: UUID
    source_id: UUID
    source_name: Optional[str] = None
    url: str
    title: str
    summary: Optional[str]
    image_url: Optional[str]
    author: Optional[str]
    published_at: Optional[datetime]
    category: str
    relevance_score: float
    engagement_potential: float
    is_used: bool
    scraped_at: datetime

    class Config:
        from_attributes = True


class ScrapedArticleDetail(ScrapedArticleResponse):
    """Detailed article response with full text."""

    full_text: Optional[str]
    tags: Optional[str]
    scrape_run_id: Optional[UUID]
