from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.post_option import PostOption
    from app.models.published_post import PublishedPost
    from app.models.user import User


class ContentSlot(Base):
    """
    Represents a scheduled posting time slot.
    5 slots are created per day (8am, 12pm, 4pm, 8pm, 12am Dubai time).
    """
    __tablename__ = "content_slots"
    __table_args__ = (
        UniqueConstraint('scheduled_date', 'slot_number', name='uq_content_slots_date_slot'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "08:00", "12:00", "16:00", "20:00", "00:00"
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Full datetime in UTC for scheduling
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 within the day
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Values: real_estate (slots 1,3), general_dubai (slots 2,4,5)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Values: pending, generating, options_ready, approved, published, failed, skipped
    approval_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Deadline for SMM to pick — after this, AI auto-selects
    selected_option_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("post_options.id", use_alter=True), nullable=True
    )
    selected_by: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Values: "human", "ai" — who made the selection
    selected_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    published_post_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("published_posts.id", use_alter=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    options: Mapped[list["PostOption"]] = relationship(
        back_populates="slot",
        foreign_keys="PostOption.slot_id"
    )
    selected_option: Mapped[Optional["PostOption"]] = relationship(
        foreign_keys=[selected_option_id],
        post_update=True
    )
    published_post: Mapped[Optional["PublishedPost"]] = relationship(
        foreign_keys=[published_post_id],
        post_update=True
    )
    selector_user: Mapped[Optional["User"]] = relationship()

    def __repr__(self) -> str:
        return f"<ContentSlot {self.scheduled_date} {self.scheduled_time}>"
