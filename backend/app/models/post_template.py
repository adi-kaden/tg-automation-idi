from sqlalchemy import String, Integer, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

from app.database import Base


class PostTemplate(Base):
    __tablename__ = "post_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: real_estate_news, market_analysis, prediction, economy, tech, construction, regulation, lifestyle
    language: Mapped[str] = mapped_column(String(5), default="both")  # en, ru, both
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    image_prompt_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    example_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tone: Mapped[str] = mapped_column(String(20), default="professional")
    # Values: professional, exciting, analytical, informative, urgent
    max_length_chars: Mapped[int] = mapped_column(Integer, default=1500)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<PostTemplate {self.name}>"
