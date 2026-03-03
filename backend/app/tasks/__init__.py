"""
Celery tasks module.
"""
from app.tasks.celery_app import celery_app
from app.tasks.scraper_tasks import scrape_all_sources, scrape_single_source
from app.tasks.content_tasks import (
    create_daily_slots_task,
    generate_content_for_slot,
    generate_all_pending_content,
    auto_select_for_slot,
    check_and_auto_select,
)

__all__ = [
    "celery_app",
    "scrape_all_sources",
    "scrape_single_source",
    "create_daily_slots_task",
    "generate_content_for_slot",
    "generate_all_pending_content",
    "auto_select_for_slot",
    "check_and_auto_select",
]
