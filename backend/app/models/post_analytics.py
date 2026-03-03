from sqlalchemy import Integer, Float, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.published_post import PublishedPost


class PostAnalytics(Base):
    __tablename__ = "post_analytics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(ForeignKey("published_posts.id"), unique=True, nullable=False)

    # Telegram metrics (updated periodically)
    views: Mapped[int] = mapped_column(Integer, default=0)
    forwards: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    reactions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: {"👍": 5, "❤️": 3}

    # Computed metrics
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    # (forwards + replies + reactions_total) / views * 100
    view_growth_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    view_growth_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Historical snapshots (JSON array of {timestamp, views, forwards, reactions})
    hourly_snapshots: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    last_fetched_at: Mapped[datetime] = mapped_column(default=func.now())
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    post: Mapped["PublishedPost"] = relationship(back_populates="analytics")

    def __repr__(self) -> str:
        return f"<PostAnalytics post_id={self.post_id} views={self.views}>"
