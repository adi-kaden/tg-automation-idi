"""
Scraper API endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.dependencies import DBSession, SMMUser
from app.models.scrape_source import ScrapeSource
from app.models.scrape_run import ScrapeRun
from app.models.scraped_article import ScrapedArticle
from app.schemas.scraper import (
    ScrapeSourceCreate,
    ScrapeSourceUpdate,
    ScrapeSourceResponse,
    ScrapeSourceDetail,
    ScrapeRunResponse,
    ScrapeRunTrigger,
    ScrapeRunSummary,
    ScrapedArticleResponse,
    ScrapedArticleDetail,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.tasks import scrape_single_source

router = APIRouter()


# ========== Source Endpoints ==========


@router.get("/sources", response_model=PaginatedResponse[ScrapeSourceResponse])
async def list_sources(
    db: DBSession,
    current_user: SMMUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    source_type: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """
    List all scrape sources with optional filters.
    """
    # Build query
    query = select(ScrapeSource)

    if source_type:
        query = query.where(ScrapeSource.source_type == source_type)
    if category:
        query = query.where(ScrapeSource.category == category)
    if is_active is not None:
        query = query.where(ScrapeSource.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Get paginated results
    query = query.order_by(ScrapeSource.name)
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    sources = result.scalars().all()

    return PaginatedResponse.create(
        items=[ScrapeSourceResponse.model_validate(s) for s in sources],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/sources", response_model=ScrapeSourceResponse, status_code=status.HTTP_201_CREATED
)
async def create_source(
    source_data: ScrapeSourceCreate,
    db: DBSession,
    current_user: SMMUser,
):
    """
    Create a new scrape source.
    """
    # Check for duplicate URL
    result = await db.execute(
        select(ScrapeSource).where(ScrapeSource.url == source_data.url)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source with this URL already exists",
        )

    source = ScrapeSource(**source_data.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)

    return ScrapeSourceResponse.model_validate(source)


@router.get("/sources/{source_id}", response_model=ScrapeSourceDetail)
async def get_source(
    source_id: UUID,
    db: DBSession,
    current_user: SMMUser,
):
    """
    Get detailed information about a scrape source.
    """
    result = await db.execute(
        select(ScrapeSource).where(ScrapeSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    # Get total articles count
    article_count_result = await db.execute(
        select(func.count(ScrapedArticle.id)).where(
            ScrapedArticle.source_id == source_id
        )
    )
    total_articles = article_count_result.scalar_one()

    # Get recent runs (last 10)
    runs_result = await db.execute(
        select(ScrapeRun)
        .where(ScrapeRun.source_id == source_id)
        .order_by(ScrapeRun.started_at.desc())
        .limit(10)
    )
    recent_runs = runs_result.scalars().all()

    response = ScrapeSourceDetail.model_validate(source)
    response.total_articles = total_articles
    response.recent_runs = [ScrapeRunSummary.model_validate(r) for r in recent_runs]

    return response


@router.patch("/sources/{source_id}", response_model=ScrapeSourceResponse)
async def update_source(
    source_id: UUID,
    source_data: ScrapeSourceUpdate,
    db: DBSession,
    current_user: SMMUser,
):
    """
    Update a scrape source.
    """
    result = await db.execute(
        select(ScrapeSource).where(ScrapeSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    # Check for duplicate URL if URL is being changed
    update_data = source_data.model_dump(exclude_unset=True)
    if "url" in update_data and update_data["url"] != source.url:
        url_check = await db.execute(
            select(ScrapeSource).where(
                and_(
                    ScrapeSource.url == update_data["url"],
                    ScrapeSource.id != source_id,
                )
            )
        )
        if url_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another source with this URL already exists",
            )

    for field, value in update_data.items():
        setattr(source, field, value)

    await db.commit()
    await db.refresh(source)

    return ScrapeSourceResponse.model_validate(source)


@router.delete("/sources/{source_id}", response_model=MessageResponse)
async def delete_source(
    source_id: UUID,
    db: DBSession,
    current_user: SMMUser,
):
    """
    Soft delete a scrape source (set is_active=False).
    """
    result = await db.execute(
        select(ScrapeSource).where(ScrapeSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    source.is_active = False
    await db.commit()

    return MessageResponse(message="Source deactivated successfully")


@router.post("/sources/{source_id}/run", response_model=ScrapeRunTrigger)
async def trigger_scrape(
    source_id: UUID,
    db: DBSession,
    current_user: SMMUser,
):
    """
    Trigger a manual scrape for a source.
    """
    result = await db.execute(
        select(ScrapeSource).where(ScrapeSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot scrape inactive source",
        )

    # Trigger Celery task
    task = scrape_single_source.delay(str(source_id), run_type="manual")

    return ScrapeRunTrigger(
        task_id=task.id,
        source_id=source_id,
        message=f"Scrape task queued for {source.name}",
    )


# ========== Run Endpoints ==========


@router.get("/runs", response_model=PaginatedResponse[ScrapeRunResponse])
async def list_runs(
    db: DBSession,
    current_user: SMMUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    source_id: Optional[UUID] = None,
    run_status: Optional[str] = Query(None, alias="status"),
):
    """
    List recent scrape runs.
    """
    query = select(ScrapeRun).options(selectinload(ScrapeRun.source))

    if source_id:
        query = query.where(ScrapeRun.source_id == source_id)
    if run_status:
        query = query.where(ScrapeRun.status == run_status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Get paginated results
    query = query.order_by(ScrapeRun.started_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    runs = result.scalars().all()

    items = []
    for run in runs:
        response = ScrapeRunResponse.model_validate(run)
        response.source_name = run.source.name if run.source else None
        items.append(response)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


# ========== Article Endpoints ==========


@router.get("/articles", response_model=PaginatedResponse[ScrapedArticleResponse])
async def list_articles(
    db: DBSession,
    current_user: SMMUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    source_id: Optional[UUID] = None,
    category: Optional[str] = None,
    is_used: Optional[bool] = None,
    min_relevance: Optional[float] = Query(None, ge=0, le=1),
    min_engagement: Optional[float] = Query(None, ge=0, le=1),
    search: Optional[str] = None,
):
    """
    List scraped articles with filters.
    """
    query = select(ScrapedArticle).options(selectinload(ScrapedArticle.source))

    # Apply filters
    if source_id:
        query = query.where(ScrapedArticle.source_id == source_id)
    if category:
        query = query.where(ScrapedArticle.category == category)
    if is_used is not None:
        query = query.where(ScrapedArticle.is_used == is_used)
    if min_relevance is not None:
        query = query.where(ScrapedArticle.relevance_score >= min_relevance)
    if min_engagement is not None:
        query = query.where(ScrapedArticle.engagement_potential >= min_engagement)
    if search:
        search_filter = or_(
            ScrapedArticle.title.ilike(f"%{search}%"),
            ScrapedArticle.summary.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Get paginated results (newest first)
    query = query.order_by(ScrapedArticle.scraped_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    articles = result.scalars().all()

    items = []
    for article in articles:
        response = ScrapedArticleResponse.model_validate(article)
        response.source_name = article.source.name if article.source else None
        items.append(response)

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/articles/{article_id}", response_model=ScrapedArticleDetail)
async def get_article(
    article_id: UUID,
    db: DBSession,
    current_user: SMMUser,
):
    """
    Get detailed information about a scraped article.
    """
    result = await db.execute(
        select(ScrapedArticle)
        .options(selectinload(ScrapedArticle.source))
        .where(ScrapedArticle.id == article_id)
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    response = ScrapedArticleDetail.model_validate(article)
    response.source_name = article.source.name if article.source else None

    return response
