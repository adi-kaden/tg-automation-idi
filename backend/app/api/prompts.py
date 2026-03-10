"""
API endpoints for managing AI prompt configurations.

CRUD for global config and per-slot overrides, plus test generation.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prompt_config import PromptConfig
from app.schemas.prompt_config import (
    PromptConfigBase,
    PromptConfigUpdate,
    PromptConfigResponse,
    SlotOverrideResponse,
    TestGenerateRequest,
    TestGenerateResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_response(config: PromptConfig) -> PromptConfigResponse:
    return PromptConfigResponse(
        id=str(config.id),
        scope=config.scope,
        slot_number=config.slot_number,
        system_prompt=config.system_prompt,
        generation_prompt=config.generation_prompt,
        tone=config.tone,
        max_length_chars=config.max_length_chars,
        image_style_prompt=config.image_style_prompt,
        image_aspect_ratio=config.image_aspect_ratio,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


# ── Hardcoded defaults (safety net) ──────────────────────────────

from app.services.content.content_generator import SYSTEM_PROMPT as DEFAULT_SYSTEM_PROMPT

DEFAULT_GENERATION_PROMPT = """Based on the following news articles, create a compelling Telegram post in Russian for IDIGOV Real Estate's channel.

Content Type: {{content_type}}
Category: {{category}}
Tone: {{tone}}
Max Length: {{max_length}} characters

SOURCE ARTICLES:
{{articles}}

Generate a Telegram post with the following structure (ALL IN RUSSIAN):

1. TITLE (Russian): A catchy, engaging headline in Russian (max 100 chars)
2. BODY (Russian): The main post content in Russian (400-{{max_length}} chars). Include key facts, insights, and a subtle call-to-action if relevant. Do NOT include hashtags.
3. IMAGE_PROMPT: A detailed prompt for generating an accompanying image (describe the visual concept, style, colors - suitable for a real estate/Dubai context)
4. QUALITY_SCORE: Rate the newsworthiness and engagement potential (0.0-1.0)

Respond in JSON format:
{
    "title_ru": "...",
    "body_ru": "...",
    "image_prompt": "...",
    "quality_score": 0.85
}"""

DEFAULT_IMAGE_STYLE_PROMPT = """Style: Modern luxury Dubai architecture, professional real estate photography style, golden hour lighting, high-end finishes
Quality: High resolution, professional photography or illustration style
Mood: Professional, aspirational, modern
Colors: Warm tones, gold accents, blues reflecting Dubai's sky and sea
Note: No text or watermarks in the image"""


async def _get_or_create_global(db: AsyncSession) -> PromptConfig:
    """Get the global config, creating with defaults if it doesn't exist."""
    try:
        result = await db.execute(
            select(PromptConfig).where(
                PromptConfig.scope == "global",
                PromptConfig.is_active == True,
            )
        )
        config = result.scalar_one_or_none()
    except Exception as e:
        # Table may not exist yet — create it on the fly
        logger.warning(f"prompt_configs table query failed, creating table: {e}")
        await db.rollback()
        from app.database import engine
        async with engine.begin() as conn:
            await conn.run_sync(PromptConfig.__table__.create, checkfirst=True)
        config = None

    if not config:
        config = PromptConfig(
            scope="global",
            slot_number=None,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            generation_prompt=DEFAULT_GENERATION_PROMPT,
            tone="professional",
            max_length_chars=1500,
            image_style_prompt=DEFAULT_IMAGE_STYLE_PROMPT,
            image_aspect_ratio="16:9",
            is_active=True,
        )
        db.add(config)
        await db.flush()

    return config


# ── Global Config ─────────────────────────────────────────────────

@router.get("/config", response_model=PromptConfigResponse)
async def get_global_config(db: AsyncSession = Depends(get_db)):
    """Get the global prompt configuration."""
    config = await _get_or_create_global(db)
    return _to_response(config)


@router.put("/config", response_model=PromptConfigResponse)
async def update_global_config(
    data: PromptConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update the global prompt configuration."""
    config = await _get_or_create_global(db)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.flush()
    return _to_response(config)


# ── Slot Overrides ────────────────────────────────────────────────

@router.get("/slots", response_model=list[SlotOverrideResponse])
async def get_all_slot_overrides(db: AsyncSession = Depends(get_db)):
    """Get override status for all 5 slots."""
    result = await db.execute(
        select(PromptConfig).where(
            PromptConfig.scope == "slot_override",
            PromptConfig.is_active == True,
        )
    )
    overrides = {c.slot_number: c for c in result.scalars().all()}

    return [
        SlotOverrideResponse(
            slot_number=n,
            has_override=n in overrides,
            config=_to_response(overrides[n]) if n in overrides else None,
        )
        for n in range(1, 6)
    ]


@router.get("/slots/{slot_number}", response_model=PromptConfigResponse)
async def get_slot_override(slot_number: int, db: AsyncSession = Depends(get_db)):
    """Get override config for a specific slot. Returns global if no override exists."""
    if not 1 <= slot_number <= 5:
        raise HTTPException(status_code=400, detail="Slot number must be 1-5")

    result = await db.execute(
        select(PromptConfig).where(
            PromptConfig.scope == "slot_override",
            PromptConfig.slot_number == slot_number,
            PromptConfig.is_active == True,
        )
    )
    override = result.scalar_one_or_none()

    if override:
        return _to_response(override)

    # Fall back to global
    config = await _get_or_create_global(db)
    return _to_response(config)


@router.put("/slots/{slot_number}", response_model=PromptConfigResponse)
async def set_slot_override(
    slot_number: int,
    data: PromptConfigBase,
    db: AsyncSession = Depends(get_db),
):
    """Set or update an override for a specific slot."""
    if not 1 <= slot_number <= 5:
        raise HTTPException(status_code=400, detail="Slot number must be 1-5")

    result = await db.execute(
        select(PromptConfig).where(
            PromptConfig.scope == "slot_override",
            PromptConfig.slot_number == slot_number,
        )
    )
    override = result.scalar_one_or_none()

    if override:
        for field, value in data.model_dump().items():
            setattr(override, field, value)
        override.is_active = True
    else:
        override = PromptConfig(
            scope="slot_override",
            slot_number=slot_number,
            is_active=True,
            **data.model_dump(),
        )
        db.add(override)

    await db.flush()
    return _to_response(override)


@router.delete("/slots/{slot_number}")
async def delete_slot_override(slot_number: int, db: AsyncSession = Depends(get_db)):
    """Reset a slot to use global config."""
    if not 1 <= slot_number <= 5:
        raise HTTPException(status_code=400, detail="Slot number must be 1-5")

    result = await db.execute(
        select(PromptConfig).where(
            PromptConfig.scope == "slot_override",
            PromptConfig.slot_number == slot_number,
        )
    )
    override = result.scalar_one_or_none()

    if override:
        await db.delete(override)
        await db.flush()

    return {"message": f"Slot {slot_number} reset to global config"}


# ── Test Generate ─────────────────────────────────────────────────

@router.post("/test-generate", response_model=TestGenerateResponse)
async def test_generate(
    data: TestGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Test generation with given prompt config.
    Fetches real articles from DB, calls Claude + Imagen, returns preview.
    Does not persist anything.
    """
    from app.models.scraped_article import ScrapedArticle
    from app.services.content.content_generator import ContentGenerator, GeneratedPost
    from app.services.content.image_generator import ImageGenerator

    # Determine content type based on slot_number
    if data.slot_number and data.slot_number in (1, 3):
        content_type = "real_estate"
    else:
        content_type = "general_dubai"

    # Fetch unused articles
    if content_type == "real_estate":
        categories = ["real_estate", "construction"]
    else:
        categories = [
            "economy", "tech", "lifestyle", "events", "tourism",
            "food_dining", "sports", "transportation", "culture",
            "entertainment", "education", "health", "environment",
            "government", "business", "general",
        ]

    result = await db.execute(
        select(ScrapedArticle)
        .where(
            ScrapedArticle.category.in_(categories),
            ScrapedArticle.used_in_post_id.is_(None),
        )
        .order_by(ScrapedArticle.relevance_score.desc())
        .limit(5)
    )
    articles = result.scalars().all()

    if not articles:
        raise HTTPException(status_code=404, detail="No articles available for test generation")

    article_dicts = [
        {
            "title": a.title,
            "summary": a.summary or "",
            "url": a.url,
        }
        for a in articles
    ]

    # Build custom prompt config
    prompt_config = {
        "system_prompt": data.system_prompt,
        "generation_prompt": data.generation_prompt,
        "tone": data.tone,
        "max_length_chars": data.max_length_chars,
        "image_style_prompt": data.image_style_prompt,
        "image_aspect_ratio": data.image_aspect_ratio,
    }

    # Generate content
    generator = ContentGenerator()
    category = "real_estate_news" if content_type == "real_estate" else "general"

    post = await generator.generate_post(
        articles=article_dicts,
        content_type=content_type,
        category=category,
        prompt_config=prompt_config,
    )

    # Generate image
    image_base64 = None
    try:
        image_gen = ImageGenerator(output_dir="generated_images")
        _, _, image_base64 = await image_gen.generate_image(
            prompt=post.image_prompt,
            category=category,
            slot_id="test",
            option_label="test",
            prompt_config=prompt_config,
        )
    except Exception as e:
        logger.warning(f"Test image generation failed: {e}")

    return TestGenerateResponse(
        title_ru=post.title_ru,
        body_ru=post.body_ru,
        image_prompt=post.image_prompt,
        quality_score=post.quality_score,
        image_base64=image_base64,
        articles_used=len(article_dicts),
    )
