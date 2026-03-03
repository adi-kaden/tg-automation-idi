from sqlalchemy import String, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.scrape_source import ScrapeSource
    from app.models.scraped_article import ScrapedArticle


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("scrape_sources.id"), nullable=True)
    run_type: Mapped[str] = mapped_column(String(20), default="scheduled")
    # Values: scheduled, manual, retry
    status: Mapped[str] = mapped_column(String(20), default="running")
    # Values: running, completed, failed, partial
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    articles_new: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    source: Mapped[Optional["ScrapeSource"]] = relationship(back_populates="runs")
    articles: Mapped[list["ScrapedArticle"]] = relationship(back_populates="scrape_run")

    def __repr__(self) -> str:
        return f"<ScrapeRun {self.id} - {self.status}>"
