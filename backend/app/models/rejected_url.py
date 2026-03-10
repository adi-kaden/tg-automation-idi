from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from uuid import UUID, uuid4

from app.database import Base


class RejectedArticleURL(Base):
    __tablename__ = "rejected_article_urls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    url: Mapped[str] = mapped_column(String(2000), unique=True, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_at: Mapped[datetime] = mapped_column(default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return f"<RejectedArticleURL {self.url[:80]}>"
