from sqlalchemy import String, Boolean, Float, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.content_slot import ContentSlot
    from app.models.scraped_article import ScrapedArticle


class PostOption(Base):
    """
    Each content slot gets 2 AI-generated post options for SMM to choose from.
    """
    __tablename__ = "post_options"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("content_slots.id"), nullable=False)
    option_label: Mapped[str] = mapped_column(String(5), nullable=False)  # "A" or "B"

    # Post content
    title_en: Mapped[str] = mapped_column(String(500), nullable=False)
    body_en: Mapped[str] = mapped_column(Text, nullable=False)
    title_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    body_ru: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # Image
    image_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    image_local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Metadata
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    source_article_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON array of scraped_article UUIDs used as sources
    ai_quality_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: real_estate_news, market_analysis, prediction, economy, tech, construction,
    #         regulation, lifestyle, events, tourism, food_dining, sports, transportation,
    #         culture, entertainment, education, health, environment, government, business, general

    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether SMM edited the content

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    slot: Mapped["ContentSlot"] = relationship(back_populates="options", foreign_keys=[slot_id])
    source_articles: Mapped[list["ScrapedArticle"]] = relationship(back_populates="used_in_post")

    def __repr__(self) -> str:
        return f"<PostOption {self.option_label} - {self.title_en[:30]}>"
