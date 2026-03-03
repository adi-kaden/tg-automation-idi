from sqlalchemy import String, Boolean, Float, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.scrape_source import ScrapeSource
    from app.models.scrape_run import ScrapeRun
    from app.models.post_option import PostOption


class ScrapedArticle(Base):
    __tablename__ = "scraped_articles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("scrape_sources.id"), nullable=False)
    scrape_run_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    url: Mapped[str] = mapped_column(String(2000), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: real_estate, economy, tech, construction, regulation, lifestyle, events,
    #         tourism, food_dining, sports, transportation, culture, entertainment,
    #         education, health, environment, government, business, general
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1, AI-scored
    engagement_potential: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1, AI-scored virality/interest
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether it was used in a post
    used_in_post_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("post_options.id"), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    scraped_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    source: Mapped["ScrapeSource"] = relationship(back_populates="articles")
    scrape_run: Mapped[Optional["ScrapeRun"]] = relationship(back_populates="articles")
    used_in_post: Mapped[Optional["PostOption"]] = relationship(back_populates="source_articles")

    def __repr__(self) -> str:
        return f"<ScrapedArticle {self.title[:50]}>"
