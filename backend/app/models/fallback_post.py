from sqlalchemy import String, Boolean, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

from app.database import Base


class FallbackPost(Base):
    """
    Pre-curated evergreen posts used by the watchdog when a slot's live
    content pipeline fails. Ensures the channel never goes silent.
    """
    __tablename__ = "fallback_posts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    body_ru: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(30), default="any", nullable=False)
    # "real_estate", "general_dubai", or "any"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    times_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<FallbackPost {self.id} - {self.title_ru[:30]}>"
