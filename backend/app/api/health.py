"""
Pipeline health & fallback-post management endpoints.

Designed for operational oversight:
  GET  /api/health/pipeline        → today's slot states + watchdog heartbeat
  GET  /api/health/fallback-posts  → list evergreen fallback library
  POST /api/health/fallback-posts  → add a new evergreen fallback post
  PATCH /api/health/fallback-posts/{id}  → edit
  DELETE /api/health/fallback-posts/{id} → remove

GET /api/health/pipeline is the endpoint that n8n, UptimeRobot, or a curl
loop can poll to detect stuck slots or a dead beat scheduler.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import DBSession, CurrentUser, AdminUser
from app.models.content_slot import ContentSlot
from app.models.fallback_post import FallbackPost
from app.models.published_post import PublishedPost
from app.utils.timezone import now_dubai, DUBAI_TZ

router = APIRouter()
settings = get_settings()


# ==================== Pipeline Health ====================

class SlotHealth(BaseModel):
    id: UUID
    slot_number: int
    scheduled_time: str
    scheduled_at: datetime
    status: str
    has_selection: bool
    published: bool
    published_by: Optional[str] = None  # "human", "ai", "fallback"
    seconds_overdue: Optional[int] = None


class PipelineHealth(BaseModel):
    date: str
    now_dubai: datetime
    total_slots: int
    published: int
    pending: int
    failed: int
    fallback_count: int
    fallback_library_size: int
    watchdog_last_tick: Optional[datetime] = None
    watchdog_stale_seconds: Optional[int] = None
    slots: list[SlotHealth]
    status: str  # "healthy", "degraded", "critical"


@router.get("/pipeline", response_model=PipelineHealth)
async def get_pipeline_health(db: DBSession):
    """
    Return today's slot states + watchdog heartbeat. Public-ish read-only
    data designed for external monitoring (no auth — returns no PII).

    Callers (n8n / UptimeRobot / curl loops) should alert when:
      - status == "critical"
      - watchdog_stale_seconds > 180
    """
    now = now_dubai()
    today = now.date()

    result = await db.execute(
        select(ContentSlot)
        .where(ContentSlot.scheduled_date == today)
        .order_by(ContentSlot.slot_number)
    )
    slots = list(result.scalars().all())

    published_post_ids = [s.published_post_id for s in slots if s.published_post_id]
    pp_by_id: dict[UUID, PublishedPost] = {}
    if published_post_ids:
        pp_result = await db.execute(
            select(PublishedPost).where(PublishedPost.id.in_(published_post_ids))
        )
        pp_by_id = {pp.id: pp for pp in pp_result.scalars().all()}

    slot_health: list[SlotHealth] = []
    published = 0
    failed = 0
    fallback_count = 0
    for s in slots:
        pp = pp_by_id.get(s.published_post_id) if s.published_post_id else None
        is_published = pp is not None
        if is_published:
            published += 1
            if pp.selected_by == "fallback":
                fallback_count += 1
        if s.status == "failed":
            failed += 1
        overdue = None
        if s.scheduled_at and s.scheduled_at <= now and not is_published:
            overdue = int((now - s.scheduled_at).total_seconds())

        slot_health.append(SlotHealth(
            id=s.id,
            slot_number=s.slot_number,
            scheduled_time=s.scheduled_time,
            scheduled_at=s.scheduled_at,
            status=s.status,
            has_selection=s.selected_option_id is not None,
            published=is_published,
            published_by=pp.selected_by if pp else None,
            seconds_overdue=overdue,
        ))

    pending = len(slots) - published - failed

    # Watchdog heartbeat from Redis
    last_tick: Optional[datetime] = None
    stale_seconds: Optional[int] = None
    try:
        import redis as redis_lib
        client = redis_lib.from_url(settings.effective_redis_url, socket_timeout=3)
        raw = client.get("watchdog:last_tick")
        if raw:
            last_tick = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
            stale_seconds = int((datetime.utcnow() - last_tick).total_seconds())
    except Exception:
        pass

    # Fallback library size
    fb_count_result = await db.execute(
        select(FallbackPost).where(FallbackPost.is_active == True)
    )
    fallback_library_size = len(list(fb_count_result.scalars().all()))

    # Overall health classification
    if stale_seconds is not None and stale_seconds > 180:
        overall = "critical"
    elif failed > 0:
        overall = "critical"
    elif any(
        s.seconds_overdue is not None and s.seconds_overdue > 300
        for s in slot_health
    ):
        overall = "critical"
    elif fallback_count > 0 or fallback_library_size == 0:
        overall = "degraded"
    else:
        overall = "healthy"

    return PipelineHealth(
        date=str(today),
        now_dubai=now,
        total_slots=len(slots),
        published=published,
        pending=pending,
        failed=failed,
        fallback_count=fallback_count,
        fallback_library_size=fallback_library_size,
        watchdog_last_tick=last_tick,
        watchdog_stale_seconds=stale_seconds,
        slots=slot_health,
        status=overall,
    )


# ==================== Fallback Post Library ====================

class FallbackPostCreate(BaseModel):
    title_ru: str = Field(..., max_length=500)
    body_ru: str
    hashtags: Optional[list[str]] = None
    image_data: Optional[str] = None  # base64
    content_type: str = Field("any", pattern="^(real_estate|general_dubai|any)$")
    is_active: bool = True


class FallbackPostUpdate(BaseModel):
    title_ru: Optional[str] = Field(None, max_length=500)
    body_ru: Optional[str] = None
    hashtags: Optional[list[str]] = None
    image_data: Optional[str] = None
    content_type: Optional[str] = Field(None, pattern="^(real_estate|general_dubai|any)$")
    is_active: Optional[bool] = None


class FallbackPostResponse(BaseModel):
    id: UUID
    title_ru: str
    body_ru: str
    hashtags: Optional[list[str]] = None
    has_image: bool
    content_type: str
    is_active: bool
    times_used: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_obj(cls, fb: FallbackPost) -> "FallbackPostResponse":
        import json as _json
        tags = None
        if fb.hashtags:
            try:
                tags = _json.loads(fb.hashtags)
            except Exception:
                tags = None
        return cls(
            id=fb.id,
            title_ru=fb.title_ru,
            body_ru=fb.body_ru,
            hashtags=tags,
            has_image=bool(fb.image_data),
            content_type=fb.content_type,
            is_active=fb.is_active,
            times_used=fb.times_used,
            last_used_at=fb.last_used_at,
            created_at=fb.created_at,
            updated_at=fb.updated_at,
        )


@router.get("/fallback-posts", response_model=list[FallbackPostResponse])
async def list_fallback_posts(db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(FallbackPost).order_by(FallbackPost.created_at.desc())
    )
    return [FallbackPostResponse.from_orm_obj(f) for f in result.scalars().all()]


@router.post("/fallback-posts", response_model=FallbackPostResponse, status_code=201)
async def create_fallback_post(
    payload: FallbackPostCreate,
    db: DBSession,
    admin: AdminUser,
):
    import json as _json
    fb = FallbackPost(
        title_ru=payload.title_ru,
        body_ru=payload.body_ru,
        hashtags=_json.dumps(payload.hashtags) if payload.hashtags else None,
        image_data=payload.image_data,
        content_type=payload.content_type,
        is_active=payload.is_active,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return FallbackPostResponse.from_orm_obj(fb)


@router.patch("/fallback-posts/{fallback_id}", response_model=FallbackPostResponse)
async def update_fallback_post(
    fallback_id: UUID,
    payload: FallbackPostUpdate,
    db: DBSession,
    admin: AdminUser,
):
    import json as _json
    result = await db.execute(
        select(FallbackPost).where(FallbackPost.id == fallback_id)
    )
    fb = result.scalar_one_or_none()
    if not fb:
        raise HTTPException(status_code=404, detail="Fallback post not found")

    data = payload.model_dump(exclude_unset=True)
    if "hashtags" in data:
        data["hashtags"] = _json.dumps(data["hashtags"]) if data["hashtags"] is not None else None
    for k, v in data.items():
        setattr(fb, k, v)

    await db.commit()
    await db.refresh(fb)
    return FallbackPostResponse.from_orm_obj(fb)


@router.delete("/fallback-posts/{fallback_id}", status_code=204)
async def delete_fallback_post(
    fallback_id: UUID,
    db: DBSession,
    admin: AdminUser,
):
    result = await db.execute(
        select(FallbackPost).where(FallbackPost.id == fallback_id)
    )
    fb = result.scalar_one_or_none()
    if not fb:
        raise HTTPException(status_code=404, detail="Fallback post not found")
    await db.delete(fb)
    await db.commit()
