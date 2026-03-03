from sqlalchemy import String, Boolean, Integer, Float, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.scraped_article import ScrapedArticle
    from app.models.scrape_run import ScrapeRun


class ScrapeSource(Base):
    __tablename__ = "scrape_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: rss, website, api, data_portal
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: real_estate, economy, tech, construction, regulation, lifestyle, events,
    #         tourism, food_dining, sports, transportation, culture, entertainment,
    #         education, health, environment, government, business, general
    language: Mapped[str] = mapped_column(String(5), default="en")  # en, ar
    scrape_frequency_hours: Mapped[int] = mapped_column(Integer, default=6)
    css_selectors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON: {"article_list": "...", "title": "...", "body": "...", "date": "...", "image": "..."}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reliability_score: Mapped[float] = mapped_column(Float, default=1.0)  # 0-1, auto-adjusted
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    articles: Mapped[list["ScrapedArticle"]] = relationship(back_populates="source")
    runs: Mapped[list["ScrapeRun"]] = relationship(back_populates="source")

    def __repr__(self) -> str:
        return f"<ScrapeSource {self.name}>"
