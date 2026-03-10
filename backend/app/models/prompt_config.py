"""
PromptConfig model for managing AI generation prompts.

Stores global defaults and per-slot-number overrides for both
content generation (Claude) and image generation (Imagen).
"""
from sqlalchemy import String, Integer, Boolean, Text, func, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

from app.database import Base


class PromptConfig(Base):
    """
    AI prompt configuration with global defaults and slot overrides.

    Cascade logic:
    1. scope="slot_override" AND slot_number=N AND is_active=true -> use it
    2. scope="global" AND is_active=true -> use global
    3. Fall back to hardcoded defaults (safety net)
    """
    __tablename__ = "prompt_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    # Values: "global", "slot_override"
    slot_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 1-5, only for slot_override

    # Content generation (Claude)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    generation_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(30), default="professional")
    # Values: professional, exciting, analytical, informative, urgent
    max_length_chars: Mapped[int] = mapped_column(Integer, default=1500)

    # Image generation (Imagen)
    image_style_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_aspect_ratio: Mapped[str] = mapped_column(String(10), default="16:9")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "scope IN ('global', 'slot_override')",
            name="ck_prompt_configs_scope"
        ),
        CheckConstraint(
            "(scope = 'global' AND slot_number IS NULL) OR "
            "(scope = 'slot_override' AND slot_number BETWEEN 1 AND 5)",
            name="ck_prompt_configs_slot_number"
        ),
        UniqueConstraint("scope", "slot_number", name="uq_prompt_configs_scope_slot"),
    )

    def __repr__(self) -> str:
        if self.scope == "global":
            return "<PromptConfig global>"
        return f"<PromptConfig slot_override #{self.slot_number}>"
