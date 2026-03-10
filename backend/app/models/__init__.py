# Import all models for Alembic to detect
from app.models.user import User
from app.models.setting import Setting
from app.models.scrape_source import ScrapeSource
from app.models.scrape_run import ScrapeRun
from app.models.scraped_article import ScrapedArticle
from app.models.content_slot import ContentSlot
from app.models.post_option import PostOption
from app.models.published_post import PublishedPost
from app.models.post_analytics import PostAnalytics
from app.models.channel_snapshot import ChannelSnapshot
from app.models.post_template import PostTemplate
from app.models.rejected_url import RejectedArticleURL
from app.models.prompt_config import PromptConfig

__all__ = [
    "User",
    "Setting",
    "ScrapeSource",
    "ScrapeRun",
    "ScrapedArticle",
    "ContentSlot",
    "PostOption",
    "PublishedPost",
    "PostAnalytics",
    "ChannelSnapshot",
    "PostTemplate",
    "RejectedArticleURL",
    "PromptConfig",
]
