"""
Pydantic schemas for content slots and post options.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ==================== Content Slot Schemas ====================

class ContentSlotBase(BaseModel):
    """Base schema for content slot."""
    scheduled_date: date
    scheduled_time: str  # "08:00", "12:00", etc.
    slot_number: int = Field(ge=1, le=5)
    content_type: str  # "real_estate" or "general_dubai"


class ContentSlotCreate(ContentSlotBase):
    """Schema for creating a content slot (usually auto-created)."""
    pass


class ContentSlotResponse(ContentSlotBase):
    """Schema for content slot in responses."""
    id: UUID
    scheduled_at: datetime
    status: str
    approval_deadline: datetime
    selected_option_id: Optional[UUID] = None
    selected_by: Optional[str] = None
    published_post_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentSlotDetail(ContentSlotResponse):
    """Detailed content slot with options."""
    options: list["PostOptionResponse"] = []


# ==================== Post Option Schemas ====================

class PostOptionBase(BaseModel):
    """Base schema for post option."""
    title_en: str = Field(max_length=500)
    body_en: str
    title_ru: str = Field(max_length=500)
    body_ru: str
    hashtags: Optional[str] = None  # JSON array as string
    category: str
    content_type: str


class PostOptionCreate(PostOptionBase):
    """Schema for creating a post option (usually auto-created by AI)."""
    slot_id: UUID
    option_label: str = Field(pattern="^[AB]$")  # "A" or "B"
    image_prompt: Optional[str] = None


class PostOptionUpdate(BaseModel):
    """Schema for updating a post option (SMM editing)."""
    title_en: Optional[str] = Field(None, max_length=500)
    body_en: Optional[str] = None
    title_ru: Optional[str] = Field(None, max_length=500)
    body_ru: Optional[str] = None
    hashtags: Optional[str] = None


class PostOptionResponse(PostOptionBase):
    """Schema for post option in responses."""
    id: UUID
    slot_id: UUID
    option_label: str
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None
    image_local_path: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded image
    source_article_ids: Optional[str] = None  # JSON array of UUIDs
    ai_quality_score: float
    is_selected: bool
    is_edited: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PostOptionDetail(PostOptionResponse):
    """Detailed post option with slot info."""
    pass


# ==================== Selection Schemas ====================

class SlotSelectionRequest(BaseModel):
    """Schema for selecting a post option."""
    option_id: UUID


class SlotSelectionResponse(BaseModel):
    """Response after selecting an option."""
    slot_id: UUID
    selected_option_id: UUID
    selected_by: str
    status: str


# ==================== Generation Schemas ====================

class ContentGenerationRequest(BaseModel):
    """Request to generate content for a slot."""
    slot_id: UUID


class ContentGenerationResponse(BaseModel):
    """Response after triggering content generation."""
    slot_id: UUID
    task_id: str
    status: str


class DailySlotsRequest(BaseModel):
    """Request to create daily slots."""
    target_date: date


class DailySlotsResponse(BaseModel):
    """Response after creating daily slots."""
    date: date
    slots_created: int
    slots: list[ContentSlotResponse]


# ==================== Query Filters ====================

class SlotFilterParams(BaseModel):
    """Filter parameters for listing slots."""
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[str] = None
    content_type: Optional[str] = None


class ContentQueueResponse(BaseModel):
    """Response for the content queue view."""
    date: date
    slots: list[ContentSlotDetail]
    stats: dict


# ==================== Publishing Schemas ====================

class PublishRequest(BaseModel):
    """Request to publish a slot."""
    language: Optional[str] = Field(None, pattern="^(en|ru|both)$")


class PublishResponse(BaseModel):
    """Response after publishing a post."""
    slot_id: UUID
    success: bool
    message_id_en: Optional[int] = None
    message_id_ru: Optional[int] = None
    published_post_id: Optional[UUID] = None
    channel_id: Optional[str] = None
    error: Optional[str] = None


class PublishedPostResponse(BaseModel):
    """Schema for published post in responses."""
    id: UUID
    slot_id: UUID
    option_id: UUID
    posted_title: str
    posted_body: str
    posted_language: str
    posted_image_url: Optional[str] = None
    telegram_message_id: Optional[int] = None
    telegram_channel_id: Optional[str] = None
    selected_by: str
    selected_by_user_id: Optional[UUID] = None
    published_at: datetime

    class Config:
        from_attributes = True


# Rebuild models for forward references
ContentSlotDetail.model_rebuild()
