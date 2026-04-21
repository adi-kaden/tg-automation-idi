from sqlalchemy import String, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.content_slot import ContentSlot
    from app.models.post_option import PostOption
    from app.models.user import User
    from app.models.post_analytics import PostAnalytics


class PublishedPost(Base):
    __tablename__ = "published_posts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("content_slots.id"), nullable=False)
    option_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("post_options.id"), nullable=True
    )
    # Nullable because fallback/evergreen publishes have no PostOption.

    # What was actually posted (may differ from option if SMM edited)
    posted_title: Mapped[str] = mapped_column(String(500), nullable=False)
    posted_body: Mapped[str] = mapped_column(Text, nullable=False)
    posted_language: Mapped[str] = mapped_column(String(5), nullable=False)  # en, ru
    posted_image_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    # Telegram metadata
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    telegram_channel_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Selection info
    selected_by: Mapped[str] = mapped_column(String(20), nullable=False)  # "human" or "ai"
    selected_by_user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)

    published_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    slot: Mapped["ContentSlot"] = relationship(foreign_keys=[slot_id])
    option: Mapped[Optional["PostOption"]] = relationship()
    selector_user: Mapped[Optional["User"]] = relationship()
    analytics: Mapped[Optional["PostAnalytics"]] = relationship(back_populates="post", uselist=False)

    def __repr__(self) -> str:
        return f"<PublishedPost {self.posted_title[:30]}>"
