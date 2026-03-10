"""Pydantic schemas for prompt config endpoints."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PromptConfigBase(BaseModel):
    """Shared fields for prompt config."""
    system_prompt: str = Field(..., min_length=1)
    generation_prompt: str = Field(..., min_length=1)
    tone: str = Field(default="professional")
    max_length_chars: int = Field(default=1500, ge=200, le=5000)
    image_style_prompt: str = Field(default="")
    image_aspect_ratio: str = Field(default="16:9")


class PromptConfigUpdate(BaseModel):
    """Fields that can be updated."""
    system_prompt: Optional[str] = None
    generation_prompt: Optional[str] = None
    tone: Optional[str] = None
    max_length_chars: Optional[int] = Field(default=None, ge=200, le=5000)
    image_style_prompt: Optional[str] = None
    image_aspect_ratio: Optional[str] = None


class PromptConfigResponse(PromptConfigBase):
    """Response schema."""
    id: str
    scope: str
    slot_number: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SlotOverrideResponse(BaseModel):
    """Response for slot overrides list."""
    slot_number: int
    has_override: bool
    config: Optional[PromptConfigResponse] = None


class TestGenerateRequest(BaseModel):
    """Request body for test generation."""
    system_prompt: str
    generation_prompt: str
    tone: str = "professional"
    max_length_chars: int = 1500
    image_style_prompt: str = ""
    image_aspect_ratio: str = "16:9"
    slot_number: Optional[int] = Field(default=None, ge=1, le=5)


class TestGenerateResponse(BaseModel):
    """Response from test generation."""
    title_ru: str
    body_ru: str
    image_prompt: str
    quality_score: float
    image_base64: Optional[str] = None
    articles_used: int
    image_style: str = ""
