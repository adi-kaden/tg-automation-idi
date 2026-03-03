from sqlalchemy import Integer, Float, Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.published_post import PublishedPost


class ChannelSnapshot(Base):
    """Daily snapshot of channel-level metrics."""
    __tablename__ = "channel_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    subscriber_growth: Mapped[int] = mapped_column(Integer, default=0)  # Change from previous day
    posts_published: Mapped[int] = mapped_column(Integer, default=0)
    avg_views: Mapped[float] = mapped_column(Float, default=0.0)
    avg_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    top_post_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("published_posts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    top_post: Mapped[Optional["PublishedPost"]] = relationship()

    def __repr__(self) -> str:
        return f"<ChannelSnapshot {self.snapshot_date}>"
