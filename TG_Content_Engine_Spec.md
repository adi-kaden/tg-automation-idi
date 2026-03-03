# TG Content Engine — Full Development Prompt for Claude Code

> **What this document is:** A complete technical specification and step-by-step build prompt for Claude Code to develop the TG Content Engine web application from scratch. Feed this entire document to Claude Code as the initial prompt, then follow the phased implementation order.

---

## PROJECT OVERVIEW

Build a web application called **"TG Content Engine"** — an internal platform for IDIGOV Real Estate (Dubai) that automates the production and publishing of Telegram channel content. The platform scrapes news and market data, generates AI-written posts with images, presents them to an SMM specialist for approval, and auto-publishes to the company's Telegram channel on a fixed schedule.

**What the app does in simple terms:**
1. System automatically scrapes **all interesting Dubai/UAE content**: real estate market news & data, plus **all trending general topics** — events, food scene, sports, tourism, entertainment, viral moments, transportation updates, tech launches, economy news, new laws, construction megaprojects, cultural happenings, celebrity visits, record-breaking achievements, and anything else that would engage Dubai residents and followers
2. AI analyzes scraped data, writes engaging Telegram posts (EN + RU), and generates matching images
3. For each scheduled time slot (5 per day), 2 post options are generated (so SMM can pick the best one)
4. SMM specialist reviews options in the web app and selects which to publish
5. If no selection is made within the configured deadline, AI auto-selects the best option
6. Selected post is automatically published to the Telegram channel
7. Analytics dashboard tracks post performance and engagement metrics

**Posting Schedule (Dubai Time, GMT+4):**
- **8:00 AM** — Post 1 (Real Estate focus)
- **12:00 PM** — Post 2 (Dubai Trending — any high-interest topic)
- **4:00 PM** — Post 3 (Real Estate focus)
- **8:00 PM** — Post 4 (Dubai Trending — any high-interest topic)
- **12:00 AM** — Post 5 (Dubai Trending — any high-interest topic)

**Content Mix Rule:** Out of 5 daily posts, **2 must be real estate market focused** (slots 1 & 3) and **3 are broad Dubai/UAE trending topics** (slots 2, 4 & 5) — covering events, lifestyle, sports, tech, economy, entertainment, food, or whatever is most engaging that day.

---

## TECH STACK

### Frontend
- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS 4
- **UI Components:** shadcn/ui
- **Data Fetching:** TanStack Query (React Query) v5
- **State Management:** Zustand
- **Form Handling:** React Hook Form + Zod validation
- **Icons:** Lucide React
- **Notifications:** Sonner (toast)
- **Charts:** Recharts (for analytics)
- **Rich Text:** Tiptap editor (for post editing with Telegram markdown support)
- **Date/Time:** date-fns + date-fns-tz (Dubai timezone handling)

### Backend
- **Framework:** FastAPI (Python 3.12+)
- **Task Queue:** Celery with Redis broker
- **Scheduler:** Celery Beat (cron-based scheduling)
- **HTTP Client:** httpx (async)
- **ORM:** SQLAlchemy 2.0 (async) + Alembic migrations
- **Validation:** Pydantic v2
- **Auth:** JWT tokens (python-jose) + bcrypt password hashing
- **Web Scraping:** httpx + BeautifulSoup4 + trafilatura (article extraction)
- **Telegram:** python-telegram-bot v21+ (async)

### Database
- **Primary:** PostgreSQL 16 (hosted on Supabase)
- **Cache/Broker:** Redis 7

### External APIs (integrated in backend)
- **Claude API** (Anthropic) — post writing, content analysis, market predictions, auto-selection logic
- **Nano Banana Pro API** (Google Gemini 3 Pro Image, via Google AI API or Together AI) — high-quality photorealistic image generation for post thumbnails
- **Telegram Bot API** — channel publishing + analytics retrieval
- **News/Data Sources** (scraped):
  - Gulf News, Khaleej Times (general news)
  - Property Finder, Bayut, DXB Interact, Dubai Land Department (real estate data)
  - CBUAE, Dubai Statistics Center (economic data)
  - Time Out Dubai, What's On Dubai, Lovin Dubai (lifestyle, events, viral content)
  - Construction Week (construction & infrastructure)
  - WAM, Dubai Media Office (official announcements)
  - Google News RSS feeds (broad aggregation across all Dubai/UAE topics)

### Infrastructure
- **Frontend hosting:** Vercel
- **Backend hosting:** Railway or Render
- **Scheduler:** Celery Beat on same backend server

---

## PROJECT STRUCTURE

```
tg-content-engine/
├── frontend/                    # Next.js app
│   ├── src/
│   │   ├── app/                 # App Router pages
│   │   │   ├── (auth)/
│   │   │   │   ├── login/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── layout.tsx
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx           # Sidebar + header layout
│   │   │   │   ├── page.tsx             # Dashboard home
│   │   │   │   ├── content-queue/
│   │   │   │   │   ├── page.tsx         # Today's content queue (main SMM view)
│   │   │   │   │   └── [slotId]/
│   │   │   │   │       └── page.tsx     # Slot detail — pick between options
│   │   │   │   ├── calendar/
│   │   │   │   │   └── page.tsx         # Weekly/monthly content calendar
│   │   │   │   ├── posts/
│   │   │   │   │   ├── page.tsx         # All published posts history
│   │   │   │   │   └── [id]/
│   │   │   │   │       └── page.tsx     # Post detail + performance
│   │   │   │   ├── scraper/
│   │   │   │   │   ├── page.tsx         # Scraper status & source management
│   │   │   │   │   └── sources/
│   │   │   │   │       └── page.tsx     # Manage scraping sources
│   │   │   │   ├── analytics/
│   │   │   │   │   └── page.tsx         # Channel analytics dashboard
│   │   │   │   ├── templates/
│   │   │   │   │   ├── page.tsx         # Post templates
│   │   │   │   │   └── [id]/
│   │   │   │   │       └── page.tsx     # Template editor
│   │   │   │   └── settings/
│   │   │   │       └── page.tsx         # Settings (admin)
│   │   │   ├── layout.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/                      # shadcn/ui components
│   │   │   ├── layout/
│   │   │   │   ├── sidebar.tsx
│   │   │   │   ├── header.tsx
│   │   │   │   └── breadcrumb.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── stats-cards.tsx
│   │   │   │   ├── today-schedule.tsx
│   │   │   │   ├── pending-actions.tsx
│   │   │   │   └── quick-actions.tsx
│   │   │   ├── content-queue/
│   │   │   │   ├── time-slot-card.tsx
│   │   │   │   ├── post-option-card.tsx
│   │   │   │   ├── post-preview.tsx
│   │   │   │   ├── post-editor.tsx
│   │   │   │   ├── countdown-timer.tsx
│   │   │   │   └── approval-actions.tsx
│   │   │   ├── calendar/
│   │   │   │   ├── calendar-view.tsx
│   │   │   │   ├── day-cell.tsx
│   │   │   │   └── slot-indicator.tsx
│   │   │   ├── posts/
│   │   │   │   ├── post-list.tsx
│   │   │   │   ├── post-card.tsx
│   │   │   │   └── post-detail.tsx
│   │   │   ├── scraper/
│   │   │   │   ├── scraper-status.tsx
│   │   │   │   ├── source-list.tsx
│   │   │   │   ├── source-form.tsx
│   │   │   │   └── scraped-articles.tsx
│   │   │   ├── analytics/
│   │   │   │   ├── engagement-chart.tsx
│   │   │   │   ├── growth-chart.tsx
│   │   │   │   ├── top-posts.tsx
│   │   │   │   ├── category-breakdown.tsx
│   │   │   │   └── time-heatmap.tsx
│   │   │   └── templates/
│   │   │       ├── template-list.tsx
│   │   │       └── template-editor.tsx
│   │   ├── lib/
│   │   │   ├── api.ts                   # API client (fetch wrapper)
│   │   │   ├── auth.ts                  # Auth helpers
│   │   │   ├── utils.ts                 # Utility functions
│   │   │   ├── telegram-formatter.ts    # Telegram markdown preview helper
│   │   │   └── constants.ts             # App constants
│   │   ├── hooks/
│   │   │   ├── use-auth.ts
│   │   │   ├── use-content-queue.ts
│   │   │   ├── use-posts.ts
│   │   │   ├── use-analytics.ts
│   │   │   └── use-scraper.ts
│   │   ├── stores/
│   │   │   └── auth-store.ts
│   │   └── types/
│   │       └── index.ts                 # Shared TypeScript types
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                     # FastAPI app
│   ├── app/
│   │   ├── main.py                      # FastAPI app entry point
│   │   ├── config.py                    # Settings (Pydantic BaseSettings)
│   │   ├── database.py                  # SQLAlchemy async engine + session
│   │   ├── dependencies.py              # Dependency injection
│   │   ├── models/                      # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── content_slot.py
│   │   │   ├── post_option.py
│   │   │   ├── published_post.py
│   │   │   ├── scraped_article.py
│   │   │   ├── scrape_source.py
│   │   │   ├── scrape_run.py
│   │   │   ├── post_template.py
│   │   │   ├── post_analytics.py
│   │   │   ├── channel_snapshot.py
│   │   │   └── setting.py
│   │   ├── schemas/                     # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── content_slot.py
│   │   │   ├── post_option.py
│   │   │   ├── published_post.py
│   │   │   ├── scraped_article.py
│   │   │   ├── scrape_source.py
│   │   │   ├── post_template.py
│   │   │   ├── analytics.py
│   │   │   └── dashboard.py
│   │   ├── api/                         # API route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── content_slots.py
│   │   │   ├── post_options.py
│   │   │   ├── published_posts.py
│   │   │   ├── scraper.py
│   │   │   ├── analytics.py
│   │   │   ├── templates.py
│   │   │   ├── settings.py
│   │   │   └── dashboard.py
│   │   ├── services/                    # Business logic + external API integrations
│   │   │   ├── __init__.py
│   │   │   ├── scraper/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_scraper.py      # Abstract scraper class
│   │   │   │   ├── news_scraper.py      # General news scraping
│   │   │   │   ├── realestate_scraper.py # RE market data scraping
│   │   │   │   ├── rss_scraper.py       # RSS feed aggregation
│   │   │   │   └── data_scraper.py      # Market data / DLD / statistics scraping
│   │   │   ├── content_generator.py     # Claude API — post writing
│   │   │   ├── image_generator.py       # Nano Banana Pro API — image generation
│   │   │   ├── auto_selector.py         # Claude API — auto-pick best option
│   │   │   ├── telegram_publisher.py    # Telegram Bot API — publish + fetch stats
│   │   │   ├── analytics_collector.py   # Collect post metrics from Telegram
│   │   │   ├── market_analyzer.py       # Claude API — RE market analysis/predictions
│   │   │   └── notification.py          # Internal notifications (Telegram DM to SMM)
│   │   ├── tasks/                       # Celery async tasks
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py            # Celery + Beat configuration
│   │   │   ├── scrape_task.py           # Scheduled scraping task
│   │   │   ├── generate_content_task.py # Content generation for time slots
│   │   │   ├── auto_select_task.py      # Auto-selection if no human input
│   │   │   ├── publish_task.py          # Publish approved post to Telegram
│   │   │   └── analytics_task.py        # Periodic analytics collection
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── security.py              # JWT + password hashing
│   │       ├── encryption.py            # API key encryption
│   │       ├── timezone.py              # Dubai timezone utilities
│   │       └── telegram_format.py       # Telegram MarkdownV2 formatting helpers
│   ├── alembic/                         # Database migrations
│   │   ├── versions/
│   │   ├── env.py
│   │   └── alembic.ini
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml               # Local dev: PostgreSQL + Redis + Backend
│
└── README.md
```

---

## DATABASE SCHEMA

Create these SQLAlchemy models. All tables use UUID primary keys and have `created_at` / `updated_at` timestamps.

### users
```python
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="smm")
    # Roles: admin, smm (SMM specialist), viewer
    telegram_user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # For DM notifications
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

### scrape_sources
```python
class ScrapeSource(Base):
    __tablename__ = "scrape_sources"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: rss, website, api, data_portal
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: real_estate, economy, tech, construction, regulation, lifestyle, events,
    #         tourism, food_dining, sports, transportation, culture, entertainment,
    #         education, health, environment, government, business, general
    language: Mapped[str] = mapped_column(String(5), default="en")  # en, ar
    scrape_frequency_hours: Mapped[int] = mapped_column(Integer, default=6)
    css_selectors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON: {"article_list": "...", "title": "...", "body": "...", "date": "...", "image": "..."}
    is_active: Mapped[bool] = mapped_column(default=True)
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reliability_score: Mapped[float] = mapped_column(Float, default=1.0)  # 0-1, auto-adjusted
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

### scrape_runs
```python
class ScrapeRun(Base):
    __tablename__ = "scrape_runs"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("scrape_sources.id"), nullable=True)
    run_type: Mapped[str] = mapped_column(String(20), default="scheduled")
    # Values: scheduled, manual, retry
    status: Mapped[str] = mapped_column(String(20), default="running")
    # Values: running, completed, failed, partial
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    articles_new: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
```

### scraped_articles
```python
class ScrapedArticle(Base):
    __tablename__ = "scraped_articles"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("scrape_sources.id"), nullable=False)
    scrape_run_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    url: Mapped[str] = mapped_column(String(2000), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: real_estate, economy, tech, construction, regulation, lifestyle, events,
    #         tourism, food_dining, sports, transportation, culture, entertainment,
    #         education, health, environment, government, business, general
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1, AI-scored
    engagement_potential: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1, AI-scored virality/interest
    is_used: Mapped[bool] = mapped_column(default=False)  # Whether it was used in a post
    used_in_post_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("post_options.id"), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    scraped_at: Mapped[datetime] = mapped_column(default=func.now())
    
    # Relationships
    source = relationship("ScrapeSource")
```

### content_slots
```python
class ContentSlot(Base):
    """
    Represents a scheduled posting time slot. 
    5 slots are created per day (8am, 12pm, 4pm, 8pm, 12am Dubai time).
    """
    __tablename__ = "content_slots"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "08:00", "12:00", "16:00", "20:00", "00:00"
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Full datetime in UTC for scheduling
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 within the day
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Values: real_estate (slots 1,3), general_dubai (slots 2,4,5)
    # "general_dubai" = ANY trending/high-interest Dubai/UAE topic:
    #   events, tourism, food, sports, entertainment, tech, economy, 
    #   transportation, culture, government announcements, viral moments, etc.
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Values: pending, generating, options_ready, approved, published, failed, skipped
    approval_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Deadline for SMM to pick — after this, AI auto-selects
    selected_option_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("post_options.id"), nullable=True
    )
    selected_by: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Values: "human", "ai" — who made the selection
    selected_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    published_post_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("published_posts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # Relationships
    options = relationship("PostOption", back_populates="slot", foreign_keys="PostOption.slot_id")
    selected_option = relationship("PostOption", foreign_keys=[selected_option_id])
    published_post = relationship("PublishedPost", foreign_keys=[published_post_id])
    selector_user = relationship("User")
```

### post_options
```python
class PostOption(Base):
    """
    Each content slot gets 2 AI-generated post options for SMM to choose from.
    """
    __tablename__ = "post_options"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("content_slots.id"), nullable=False)
    option_label: Mapped[str] = mapped_column(String(5), nullable=False)  # "A" or "B"
    
    # Post content
    title_en: Mapped[str] = mapped_column(String(500), nullable=False)
    body_en: Mapped[str] = mapped_column(Text, nullable=False)
    title_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    body_ru: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Image
    image_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    image_local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Metadata
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    source_article_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON array of scraped_article UUIDs used as sources
    ai_quality_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Values: real_estate_news, market_analysis, prediction, economy, tech, construction,
    #         regulation, lifestyle, events, tourism, food_dining, sports, transportation,
    #         culture, entertainment, education, health, environment, government, business, general
    
    is_selected: Mapped[bool] = mapped_column(default=False)
    is_edited: Mapped[bool] = mapped_column(default=False)  # Whether SMM edited the content
    
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # Relationships
    slot = relationship("ContentSlot", back_populates="options", foreign_keys=[slot_id])
```

### published_posts
```python
class PublishedPost(Base):
    __tablename__ = "published_posts"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slot_id: Mapped[UUID] = mapped_column(ForeignKey("content_slots.id"), nullable=False)
    option_id: Mapped[UUID] = mapped_column(ForeignKey("post_options.id"), nullable=False)
    
    # What was actually posted (may differ from option if SMM edited)
    posted_title: Mapped[str] = mapped_column(String(500), nullable=False)
    posted_body: Mapped[str] = mapped_column(Text, nullable=False)
    posted_language: Mapped[str] = mapped_column(String(5), nullable=False)  # en, ru
    posted_image_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    
    # Telegram metadata
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    telegram_channel_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Selection info
    selected_by: Mapped[str] = mapped_column(String(20), nullable=False)  # "human" or "ai"
    selected_by_user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    published_at: Mapped[datetime] = mapped_column(default=func.now())
    
    # Relationships
    slot = relationship("ContentSlot")
    option = relationship("PostOption")
    analytics = relationship("PostAnalytics", back_populates="post", uselist=False)
```

### post_analytics
```python
class PostAnalytics(Base):
    __tablename__ = "post_analytics"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(ForeignKey("published_posts.id"), unique=True, nullable=False)
    
    # Telegram metrics (updated periodically)
    views: Mapped[int] = mapped_column(Integer, default=0)
    forwards: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    reactions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: {"👍": 5, "❤️": 3}
    
    # Computed metrics
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    # (forwards + replies + reactions_total) / views * 100
    view_growth_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    view_growth_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Historical snapshots (JSON array of {timestamp, views, forwards, reactions})
    hourly_snapshots: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    last_fetched_at: Mapped[datetime] = mapped_column(default=func.now())
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # Relationships
    post = relationship("PublishedPost", back_populates="analytics")
```

### channel_snapshots
```python
class ChannelSnapshot(Base):
    """Daily snapshot of channel-level metrics."""
    __tablename__ = "channel_snapshots"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    subscriber_growth: Mapped[int] = mapped_column(Integer, default=0)  # Change from previous day
    posts_published: Mapped[int] = mapped_column(Integer, default=0)
    avg_views: Mapped[float] = mapped_column(Float, default=0.0)
    avg_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    top_post_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("published_posts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

### post_templates
```python
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
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

### settings
```python
class Setting(Base):
    __tablename__ = "settings"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_encrypted: Mapped[bool] = mapped_column(default=False)
    category: Mapped[str] = mapped_column(String(50), default="general")
    # Categories: api_keys, telegram, scheduling, content, notifications, system
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

---

## API ENDPOINTS

### Authentication
```
POST   /api/auth/login              — Login → JWT token
POST   /api/auth/refresh            — Refresh JWT token
GET    /api/auth/me                 — Get current user profile
```

### Dashboard
```
GET    /api/dashboard/stats         — Overview stats (posts today, pending, channel subscribers, engagement avg)
GET    /api/dashboard/today         — Today's schedule with slot statuses
GET    /api/dashboard/pending       — Items needing SMM attention
```

### Content Slots
```
GET    /api/content-slots           — List slots (filterable: date, status, content_type)
GET    /api/content-slots/today     — Get today's 5 slots with their options
GET    /api/content-slots/{id}      — Get slot detail with both options
POST   /api/content-slots/{id}/select — SMM selects an option (body: {option_id, edits?})
POST   /api/content-slots/{id}/skip   — Skip this slot (won't publish)
POST   /api/content-slots/{id}/regenerate — Regenerate options for this slot
GET    /api/content-slots/upcoming  — Next 7 days of scheduled slots
```

### Post Options
```
GET    /api/post-options/{id}       — Get option detail
PATCH  /api/post-options/{id}       — Edit option content (SMM edits before approving)
POST   /api/post-options/{id}/regenerate-image — Regenerate the image for this option
```

### Published Posts
```
GET    /api/published-posts         — List all published posts (filterable: date, category, language, performance)
GET    /api/published-posts/{id}    — Post detail with analytics
GET    /api/published-posts/search  — Full-text search across posts
```

### Scraper
```
GET    /api/scraper/sources         — List all scrape sources
POST   /api/scraper/sources         — Add a new source
PATCH  /api/scraper/sources/{id}    — Update source config
DELETE /api/scraper/sources/{id}    — Remove source
POST   /api/scraper/sources/{id}/test — Test scrape a source (returns sample articles)
GET    /api/scraper/runs            — List recent scrape runs with stats
POST   /api/scraper/run-now         — Trigger an immediate scrape of all active sources
GET    /api/scraper/articles        — List scraped articles (filterable: category, date, source, relevance, used)
GET    /api/scraper/articles/{id}   — Article detail
```

### Analytics
```
GET    /api/analytics/overview      — Channel overview (subscribers, growth rate, avg engagement)
GET    /api/analytics/posts         — Post performance data (filterable: date range, category)
GET    /api/analytics/engagement    — Engagement trends over time
GET    /api/analytics/best-times    — Best performing posting times
GET    /api/analytics/categories    — Performance breakdown by content category
GET    /api/analytics/growth        — Subscriber growth over time
GET    /api/analytics/top-posts     — Top performing posts (by views, engagement)
```

### Templates (admin only for write)
```
GET    /api/templates               — List all templates
POST   /api/templates               — Create new template
GET    /api/templates/{id}          — Get template detail
PATCH  /api/templates/{id}          — Update template
DELETE /api/templates/{id}          — Delete template
POST   /api/templates/{id}/test     — Test template with sample data → returns Claude output
```

### Users (admin only)
```
GET    /api/users                   — List all users
POST   /api/users                   — Create new user
PATCH  /api/users/{id}              — Update user
DELETE /api/users/{id}              — Deactivate user
```

### Settings (admin only)
```
GET    /api/settings                — Get all settings (masked for encrypted)
PATCH  /api/settings                — Batch update settings
POST   /api/settings/test-connection — Test API connectivity (Claude, Nano Banana Pro, Telegram Bot)
POST   /api/settings/test-telegram  — Send test message to Telegram channel
```

---

## CELERY TASKS & SCHEDULING

### Celery Beat Schedule (celery_app.py)

```python
"""
All times are in Dubai timezone (Asia/Dubai, GMT+4).

Daily Schedule:
  04:00 AM — Run full scrape of all sources (so data is fresh for morning content)
  05:00 AM — Generate content options for all 5 slots of the day
  07:30 AM — Auto-select for 8:00 AM slot if no human selection
  08:00 AM — Publish slot 1 (Real Estate)
  11:30 AM — Auto-select for 12:00 PM slot if no human selection
  12:00 PM — Publish slot 2 (Trending)
  15:30 PM — Auto-select for 4:00 PM slot if no human selection
  16:00 PM — Publish slot 3 (Real Estate)
  19:30 PM — Auto-select for 8:00 PM slot if no human selection
  20:00 PM — Publish slot 4 (Trending)
  23:30 PM — Auto-select for 12:00 AM slot if no human selection
  00:00 AM — Publish slot 5 (Trending)

Recurring:
  Every 6 hours — Supplementary scrape run
  Every 1 hour — Update analytics for posts published in last 48 hours
  Every 24 hours (midnight) — Take channel snapshot, cleanup old data
"""

beat_schedule = {
    "morning-scrape": {
        "task": "tasks.scrape_task.run_full_scrape",
        "schedule": crontab(hour=4, minute=0),  # 4:00 AM Dubai
    },
    "generate-daily-content": {
        "task": "tasks.generate_content_task.generate_all_slots",
        "schedule": crontab(hour=5, minute=0),  # 5:00 AM Dubai
    },
    "auto-select-slot-1": {
        "task": "tasks.auto_select_task.auto_select_if_needed",
        "schedule": crontab(hour=7, minute=30),
        "args": [1],  # slot_number
    },
    "publish-slot-1": {
        "task": "tasks.publish_task.publish_slot",
        "schedule": crontab(hour=8, minute=0),
        "args": [1],
    },
    "auto-select-slot-2": {
        "task": "tasks.auto_select_task.auto_select_if_needed",
        "schedule": crontab(hour=11, minute=30),
        "args": [2],
    },
    "publish-slot-2": {
        "task": "tasks.publish_task.publish_slot",
        "schedule": crontab(hour=12, minute=0),
        "args": [2],
    },
    "auto-select-slot-3": {
        "task": "tasks.auto_select_task.auto_select_if_needed",
        "schedule": crontab(hour=15, minute=30),
        "args": [3],
    },
    "publish-slot-3": {
        "task": "tasks.publish_task.publish_slot",
        "schedule": crontab(hour=16, minute=0),
        "args": [3],
    },
    "auto-select-slot-4": {
        "task": "tasks.auto_select_task.auto_select_if_needed",
        "schedule": crontab(hour=19, minute=30),
        "args": [4],
    },
    "publish-slot-4": {
        "task": "tasks.publish_task.publish_slot",
        "schedule": crontab(hour=20, minute=0),
        "args": [4],
    },
    "auto-select-slot-5": {
        "task": "tasks.auto_select_task.auto_select_if_needed",
        "schedule": crontab(hour=23, minute=30),
        "args": [5],
    },
    "publish-slot-5": {
        "task": "tasks.publish_task.publish_slot",
        "schedule": crontab(hour=0, minute=0),
        "args": [5],
    },
    "supplementary-scrape": {
        "task": "tasks.scrape_task.run_full_scrape",
        "schedule": crontab(hour="10,16,22", minute=0),
    },
    "update-analytics": {
        "task": "tasks.analytics_task.update_recent_post_analytics",
        "schedule": crontab(minute=0),  # Every hour
    },
    "daily-snapshot": {
        "task": "tasks.analytics_task.take_channel_snapshot",
        "schedule": crontab(hour=0, minute=30),  # 12:30 AM Dubai (after slot 5 publishes)
    },
}
```

### Task: run_full_scrape
```python
"""
1. Get all active ScrapeSource records
2. For each source, based on source_type:
   - RSS: parse feed, extract new articles
   - Website: fetch page, parse with CSS selectors or trafilatura
   - API: call API endpoint, parse response
   - Data portal: fetch structured data (DLD transactions, etc.)
3. For each new article:
   - Check URL doesn't already exist in scraped_articles (dedup)
   - Extract: title, summary, full_text, image_url, published_at
   - Call Claude to score relevance (0-1) and assign category
   - Save to scraped_articles
4. Update source.last_scraped_at
5. Create ScrapeRun record with stats
"""
```

### Task: generate_all_slots
```python
"""
1. Create 5 ContentSlot records for today (if they don't exist):
   - Slot 1: 08:00, content_type=real_estate
   - Slot 2: 12:00, content_type=general_dubai
   - Slot 3: 16:00, content_type=real_estate
   - Slot 4: 20:00, content_type=general_dubai
   - Slot 5: 00:00 (next day), content_type=general_dubai
   - Set approval_deadline = scheduled_time - 30 minutes

2. For each slot, generate 2 post options (A and B):
   a. Gather source material:
      - For REAL ESTATE slots (1, 3):
        → Query scraped_articles where category='real_estate' from last 24-48h
        → Also query market data articles for analysis/prediction angles
        → Sort by relevance_score DESC, pick top 5-10 articles
      
      - For GENERAL DUBAI slots (2, 4):
        → Query scraped_articles where category != 'real_estate' from last 24-48h
        → This includes ALL trending topics: events, food, sports, tourism, 
          entertainment, tech, economy, transportation, culture, viral moments, 
          government announcements — literally anything interesting happening in Dubai
        → Sort by engagement_potential DESC (not just relevance — we want viral/interesting)
        → Pick top 5-10 articles
        → Ensure variety: don't pick 5 articles from the same category
      
      - Ensure option A and B use DIFFERENT primary articles (variety)
   
   b. Select appropriate PostTemplate based on content_type and available material
   
   c. Call Claude API with:
      - System prompt: template + channel voice/style guide
      - User prompt: article summaries + data points + instructions
      - Request: title_en, body_en, title_ru, body_ru, hashtags, image_prompt
      - Require Telegram MarkdownV2 formatting
   
   d. For market_analysis/prediction posts (real_estate slots):
      - Also pass recent DLD data, price trends, transaction volumes
      - Ask Claude to generate data-backed predictions
      - Emphasize "based on data from [verified source]" attribution
   
   e. Call Nano Banana Pro API with the image_prompt to generate a post image
   
   f. Save PostOption records

3. Set all slots to status=options_ready
4. Send notification to SMM via Telegram DM: "📋 Content ready for review! 5 slots need your input."
"""
```

### Task: auto_select_if_needed
```python
"""
For a given slot_number on today's date:
1. Check if ContentSlot already has a selected_option_id → skip if yes
2. If no selection made:
   a. Get both PostOption records
   b. Call Claude to evaluate which is better:
      - Consider: engagement potential, news freshness, variety from recent posts,
        image quality, alignment with channel tone
   c. Set selected_option_id, selected_by="ai"
   d. Send notification to SMM: "🤖 Auto-selected option {X} for {time} slot"
"""
```

### Task: publish_slot
```python
"""
For a given slot_number on today's date:
1. Get ContentSlot → check it has a selected option
   - If not: trigger auto_select first, then continue
2. Get the selected PostOption
3. Determine which language to post (configurable: "en", "ru", or "both")
   - If "both": post EN first, then RU as a reply/separate message
4. Format post for Telegram:
   - Apply MarkdownV2 formatting
   - Append hashtags
   - Attach image
5. Call Telegram Bot API: sendPhoto (with image) or sendMessage (text only)
6. Capture telegram_message_id from response
7. Create PublishedPost record
8. Update ContentSlot: status=published, published_post_id
9. Mark used scraped_articles as is_used=True
10. Initialize PostAnalytics record
"""
```

### Task: update_recent_post_analytics
```python
"""
1. Get all PublishedPosts from last 48 hours
2. For each: call Telegram Bot API to get message stats (views, forwards, reactions)
3. Update PostAnalytics records
4. Calculate engagement_rate and growth metrics
5. Append to hourly_snapshots JSON
"""
```

---

## CONTENT GENERATION — CLAUDE PROMPTS

### System Prompt (Channel Voice)
```
You are the content writer for IDIGOV Real Estate's Telegram channel — a premium Dubai-based real estate
agency. The channel provides valuable insights on Dubai's real estate market and lifestyle.

CHANNEL VOICE:
- Professional yet approachable
- Data-driven and credible — always reference sources
- Engaging — use hooks that make readers stop scrolling
- Bilingual — write in both English and Russian with equal quality
- Never salesy — provide genuine value, subtle brand positioning

FORMATTING RULES (Telegram MarkdownV2):
- Use bold (*text*) for headlines and key numbers
- Use italic (_text_) sparingly for emphasis
- Short paragraphs (2-3 sentences max)
- Use emoji strategically (1-3 per post, never excessive)
- End with 3-5 relevant hashtags
- Total post length: 800-1500 characters (including spaces)

POST STRUCTURE:
1. Hook line (attention-grabbing first sentence, often a surprising fact or question)
2. Core content (2-3 short paragraphs with the meat of the story)
3. Key takeaway or IDIGOV angle (subtle, not pushy)
4. Hashtags

NEVER:
- Make up statistics or data — only use what's provided in the source material
- Directly promote IDIGOV services (this is a value-first channel)
- Use clickbait without substance
- Post outdated information
```

### Real Estate Market Analysis Template
```
Based on the following market data and recent articles, write an engaging Telegram post 
about the Dubai real estate market.

DATA:
{market_data}

RECENT ARTICLES:
{article_summaries}

REQUIREMENTS:
- Focus on: {specific_angle} (e.g., "price trends in Dubai Marina", "off-plan vs ready market")
- Include at least 1 specific number/statistic from the data
- If making a prediction, clearly state it's based on current trends and cite the data source
- Make it actionable — what should the reader take away?
- Write in BOTH English and Russian

Respond in this JSON format:
{
  "title_en": "...",
  "body_en": "...",
  "title_ru": "...",
  "body_ru": "...",
  "hashtags": ["#DubaiRealEstate", ...],
  "image_prompt": "A photorealistic image of ... (describe the ideal post image)",
  "content_type": "market_analysis|prediction|news"
}
```

### General News Template
```
Based on the following recent news from Dubai/UAE, write an engaging Telegram post.
This could be about ANY trending topic — events, food & dining, sports, tourism, 
entertainment, technology, transportation, cultural happenings, viral moments, 
celebrity visits, record-breaking achievements, new openings, government initiatives, 
or anything else that Dubai residents and followers would find interesting.

ARTICLES:
{article_summaries}

REQUIREMENTS:
- Pick the most interesting/engaging angle — what would make someone stop scrolling?
- Keep it informative but conversational
- If it's a fun/viral topic, match the energy (exciting, surprising, impressive)
- If it's a practical topic (transport, rules), make it useful and clear
- Relate it to life in Dubai — why should our followers care?
- Write in BOTH English and Russian

Respond in this JSON format:
{
  "title_en": "...",
  "body_en": "...",
  "title_ru": "...",
  "body_ru": "...",
  "hashtags": ["#Dubai", ...],
  "image_prompt": "...",
  "content_type": "lifestyle|tech|regulation|construction|events|tourism|food_dining|sports|transportation|culture|entertainment|health|environment|government|business|general"
}
```

---

## IMAGE GENERATION

Use **Nano Banana Pro** (Google Gemini 3 Pro Image model) for image generation. Access via the Google Generative AI API directly or through Together AI.

```python
"""
For each PostOption, generate one image using the AI-generated image_prompt.

OPTION A — Google Generative AI API (recommended, native access):
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent
Headers: x-goog-api-key: {GEMINI_API_KEY}
Body: {
  "contents": [{
    "parts": [
      {"text": "{image_prompt}. Professional real estate marketing style, 
                clean composition, no text overlays, photorealistic, 
                16:9 aspect ratio, high quality, Dubai aesthetic"}
    ]
  }],
  "generationConfig": {
    "responseModalities": ["IMAGE", "TEXT"]
  }
}
Response: contains base64-encoded image data in parts → decode and save as .jpg

OPTION B — Together AI (simpler REST API, pay-per-image):
POST https://api.together.xyz/v1/images/generations
Headers: Authorization: Bearer {TOGETHER_API_KEY}
Body: {
  "model": "google/gemini-3-pro-image",
  "prompt": "{image_prompt}. Professional real estate marketing style, 
             clean composition, no text overlays, photorealistic, 
             16:9 aspect ratio, high quality, Dubai aesthetic",
  "width": 1280,
  "height": 720,
  "n": 1
}
Response: { "data": [{ "url": "..." }] } → download and save

PRICING (approximate):
  - Google AI API: ~$0.04/image (1K-2K), ~$0.07/image (4K)
  - Together AI: ~$0.05/image (2K)
  - 5 slots × 2 options × 1 image = 10 images/day ≈ $0.40-0.70/day

IMPORTANT:
- Never include text in images (Telegram supports text natively)
- Use photorealistic style for real estate, modern/clean for general topics
- Save image locally for upload to Telegram (don't rely on external URLs being permanent)
- Generate images at 1280x720 (16:9) for Telegram post thumbnails
- Nano Banana Pro excels at photorealism and accurate scene composition — ideal for 
  real estate and Dubai cityscape imagery
- All generated images include a SynthID watermark (invisible, for responsible AI tracking)
"""
```

---

## FRONTEND PAGES — DETAILED SPECIFICATIONS

### Login Page (`/login`)
- Clean centered card with IDIGOV branding
- Email + password fields
- "Sign In" button
- Redirect to dashboard on success

### Dashboard (`/`)
- **Stats row (4 cards):** Posts Today (X/5 published), Pending Review (needs attention count), Channel Subscribers (with +/- change), Avg Engagement Rate (last 7 days)
- **Today's Schedule:** Visual timeline showing 5 time slots with status indicators (pending → generating → ready → approved → published). Each slot shows the selected option preview or "Needs Review" badge
- **Pending Actions:** Alert-style list of slots needing SMM attention, with countdown timers to auto-select deadline
- **Quick Actions:** 3 buttons: "Review Content Queue", "Run Scraper Now", "View Analytics"
- Data refreshes every 30 seconds

### Content Queue (`/content-queue`) — **PRIMARY SMM VIEW**
- **This is the most important page** — where SMM spends most of their time
- **Layout:** 5 time slot cards arranged vertically, each showing:
  - Time + content type badge (🏠 Real Estate / 🌆 Dubai Trending)
  - Status indicator (color-coded)
  - If status=options_ready: Show both Option A and Option B side-by-side as preview cards
  - Countdown timer to auto-select deadline
  - "Select A" / "Select B" buttons (prominent)
  - "Edit & Select" button (opens editor before confirming)
  - "Skip" button (muted, with confirmation)
  - If status=published: Show the published post with a ✅ checkmark

### Content Slot Detail (`/content-queue/{slotId}`)
- **Side-by-side comparison** of Option A and Option B:
  - Full post preview (formatted as it will appear on Telegram)
  - Generated image preview
  - Source articles list (collapsible)
  - AI quality score badge
- **Post editor:** If SMM wants to modify before publishing:
  - Rich text editor with Telegram MarkdownV2 preview
  - Tabs for EN and RU versions
  - Image preview with "Regenerate Image" button
  - Edit hashtags
- **Action bar (sticky bottom):** "Select Option A" / "Select Option B" / "Regenerate Both" / "Skip Slot"
- **Preview panel:** Live Telegram message preview (styled to look like Telegram)

### Content Calendar (`/calendar`)
- **Monthly calendar view** with each day showing 5 colored dots (one per slot):
  - Green: Published
  - Blue: Approved/ready
  - Yellow: Pending review
  - Gray: Not yet generated
  - Red: Failed
- Click a day → shows that day's 5 slots in a sidebar/modal
- **Week view toggle:** More detailed, shows actual post titles per slot
- Ability to navigate past and future dates

### Published Posts (`/posts`)
- **List view** with columns: Date/Time, Title, Category (badge), Language, Views, Engagement Rate, Selected By (Human/AI badge)
- **Filters:** Date range, Category, Language, Performance (top/average/low), Selection method (human/ai)
- **Search** across post titles and content
- Click → `/posts/{id}` detail page

### Post Detail (`/posts/{id}`)
- **Post preview** (Telegram-styled)
- **Performance metrics panel:** Views (with growth chart), Forwards, Replies, Reactions breakdown (emoji counts), Engagement rate
- **Hourly views chart:** Line chart showing view growth over time
- **Source info:** Which articles were used, which template, AI quality score
- **Comparison:** If this was a real_estate slot, show a mini chart comparing this post vs average real_estate post performance

### Scraper Dashboard (`/scraper`)
- **Status overview:** Last run time, articles scraped today, source health indicators
- **Recent Runs table:** Start time, duration, articles found, articles new, status
- **"Run Now" button** — triggers immediate scrape with loading indicator
- **Source health grid:** Each source as a card showing name, last success, reliability score, error rate

### Scraper Sources (`/scraper/sources`)
- **Table:** Name, URL, Type, Category, Language, Frequency, Last Scraped, Reliability, Active toggle
- **"+ Add Source" button** → modal/form with:
  - Name, URL, Type (RSS/Website/API), Category, Language
  - If Website: CSS selector configuration with live preview
  - "Test Scrape" button to validate selectors
- **Edit source** → same form pre-filled

### Analytics Dashboard (`/analytics`) — **KEY PAGE**
- **Top-level KPIs (cards):**
  - Total subscribers (with growth trend)
  - Posts this month
  - Avg views per post
  - Avg engagement rate
  - Best performing day/time
  - Human vs AI selection ratio

- **Charts section:**
  - **Subscriber Growth:** Line chart (last 30/90 days)
  - **Engagement Over Time:** Line chart with views and engagement rate on dual axis
  - **Category Performance:** Bar chart comparing avg views by content category (real estate, events, lifestyle, tech, economy, sports, etc.)
  - **Posting Time Heatmap:** Grid showing avg views per day-of-week × time-slot
  - **Top Posts:** Table of top 10 posts by views/engagement with post preview on hover
  - **Human vs AI Selection Performance:** Compare avg engagement when SMM picks vs AI auto-selects
  - **Content Type Breakdown:** Pie chart of post types (real estate news, market analysis, events, lifestyle, tech, etc. — showing which topics perform best)

- **Filters:** Date range picker (7d, 30d, 90d, custom), Category filter

### Templates (`/templates`)
- **List view:** Template cards with name, category, tone, language, active toggle
- Click → template editor with:
  - Name, category, tone, max_length fields
  - Large prompt template textarea with variable highlighting
  - Image prompt template textarea
  - Example output section
  - **"Test Template" button:** Split view — left: template + sample inputs, right: Claude output preview

### Settings (`/settings`)
- Admin only
- **Tabs:**
  - **API Keys:** Masked inputs for Claude, Gemini (Nano Banana Pro), Telegram Bot Token. "Test Connection" per key.
  - **Telegram Channel:** Channel ID/username, posting language preference (EN/RU/Both), bot connection test, send test message
  - **Schedule:** Edit posting times, approval deadline offset (minutes before post time), auto-select on/off toggle per slot
  - **Content Rules:** Min/max post length, required hashtag count, content mix rules (which slots get which category)
  - **Notifications:** SMM notification settings (Telegram DM, timing of reminders)
  - **Team:** User list with role management, invite form
  - **System:** Scrape frequency, article retention days, analytics fetch frequency, cleanup settings

---

## SCRAPING STRATEGY — DETAILED

### Source Categories & URLs to Seed

**Real Estate News & Market:**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| Gulf News Property | RSS | `https://gulfnews.com/property/rss` | |
| Khaleej Times Property | Website | `https://www.khaleejtimes.com/property` | |
| Property Finder Blog | Website | `https://www.propertyfinder.ae/blog/` | |
| Bayut Blog | Website | `https://www.bayut.com/mybayut/` | |
| Construction Week Online | Website | `https://www.constructionweekonline.com/` | New launches, mega projects |

**Real Estate Market Data:**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| DXB Interact | API/Website | `https://dxbinteract.com/` | Transaction data, price indices |
| Dubai Land Dept Open Data | Website | `https://dubailand.gov.ae/en/open-data/` | Official transaction records |

**General Dubai/UAE News (broad — covers everything trending):**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| Gulf News | RSS | `https://gulfnews.com/rss` | Covers all sections |
| Khaleej Times | RSS | `https://www.khaleejtimes.com/rss` | Broad UAE coverage |
| WAM (Emirates News Agency) | Website | `https://www.wam.ae/en` | Official govt announcements |
| Dubai Media Office | Website | `https://mediaoffice.ae/en/news` | Official Dubai news |

**Lifestyle, Events & Viral Content:**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| Time Out Dubai | Website | `https://www.timeoutdubai.com/news` | Events, restaurants, things to do |
| What's On Dubai | Website | `https://whatson.ae/dubai/` | Lifestyle, dining, entertainment |
| Lovin Dubai | Website | `https://lovindubai.com/` | Viral stories, trending Dubai moments |
| Visit Dubai Blog | Website | `https://www.visitdubai.com/en/articles` | Tourism, attractions |
| Dubai Calendar | Website | `https://www.dubaicalendar.com/` | Upcoming events |

**Economy, Business & Finance:**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| CBUAE (Central Bank) | Website | `https://www.centralbank.ae/en/news` | Monetary policy, banking |
| Dubai Economy & Tourism | Website | `https://www.dubaidet.gov.ae/` | Economic indicators |

**Technology & Innovation:**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| Gulf Business Tech | Website | `https://gulfbusiness.com/category/technology/` | UAE tech news |
| ITP.net | Website | `https://www.itp.net/` | ME technology |
| GITEX News | Website | Check seasonally | Major tech events |

**Sports & Entertainment:**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| Sport360 | Website | `https://sport360.com/` | UAE/Dubai sports |
| Dubai Sports Council | Website | Official site | Local sports events |

**Transportation & Infrastructure:**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| RTA News | Website | `https://www.rta.ae/wps/portal/rta/ae/home/news` | Transport updates |
| Gulf News Transport | RSS | `https://gulfnews.com/uae/transport/rss` | Metro, roads, aviation |

**Broad Aggregation (catches everything else):**
| Source | Type | URL | Notes |
|--------|------|-----|-------|
| Google News | RSS | Queries: "Dubai", "UAE news", "Dubai events", "Dubai lifestyle" via RSS | Catches trending stories from any source |
| Reddit r/dubai | Website | `https://www.reddit.com/r/dubai/top/?t=day` | What residents are actually talking about |

### Scraping Logic

```python
"""
base_scraper.py — Abstract class all scrapers inherit from:

class BaseScraper:
    async def scrape(self, source: ScrapeSource) -> List[RawArticle]:
        """Override in subclasses"""
        
    async def extract_article(self, url: str) -> ArticleContent:
        """Use trafilatura for clean article text extraction"""
        response = await httpx_client.get(url)
        content = trafilatura.extract(response.text, include_comments=False, 
                                        include_tables=True, output_format='json')
        return ArticleContent(**json.loads(content))
    
    async def score_relevance(self, article: RawArticle) -> Tuple[float, float]:
        """
        Call Claude to score each article on two dimensions:
        
        relevance_score (0-1): How relevant is this to our Dubai/UAE audience?
          - Direct Dubai/UAE connection = high
          - Affects expats/investors in Dubai = high
          - Tangentially related = medium
          - No connection = low
        
        engagement_potential (0-1): How likely is this to get views/shares?
          - Surprising or counterintuitive facts = high
          - Breaking news / first to report = high
          - Viral-worthy (funny, impressive, record-breaking) = high
          - Affects many people (new rules, visa changes, metro updates) = high
          - Celebrity/event related = high
          - Dry/routine announcements = low
          - Old news already widely covered = low
        
        The system prioritizes articles with HIGH engagement_potential for the 
        general_dubai slots, ensuring we surface the most interesting content 
        across ALL topics — not just economy and tech.
        """
        
    async def deduplicate(self, article: RawArticle) -> bool:
        """Check URL and title similarity against existing articles"""
        # Exact URL match → skip
        # Title similarity > 0.85 (fuzzy match) → skip
        
rss_scraper.py:
    - Parse RSS/Atom feeds using feedparser
    - Extract: title, link, summary, published date
    - For each new article: fetch full text via trafilatura
    
news_scraper.py:
    - Fetch page HTML
    - Parse using CSS selectors from source config
    - Or use trafilatura's built-in article detection
    - Handle pagination if configured
    
data_scraper.py:
    - Specialized scrapers for structured data sources
    - DXB Interact: transaction volumes, price indices
    - DLD Open Data: latest transaction data
    - Format as structured JSON for market_analyzer service
"""
```

---

## UI DESIGN GUIDELINES

- **Color palette:** Primary: deep navy (#0F172A). Accent: bright teal (#14B8A6). Secondary: warm amber (#F59E0B). Background: slate-50 (#F8FAFC). Text: slate-900 (#0F172A). Success: emerald (#10B981). Warning: amber (#F59E0B). Error: rose (#F43F5E).
- **Sidebar:** Fixed left sidebar (260px) with IDIGOV logo, navigation with icons, collapsible on mobile. Active item highlighted with teal accent.
- **Key visual element:** The Content Queue page should feel like a "mission control" — clear, urgent, actionable. Each time slot card should have visual weight and clear CTAs.
- **Telegram preview:** Posts should be previewable in a component that mimics the Telegram message bubble style (light blue/white background, rounded corners, Telegram-like typography).
- **Status indicators:** Use consistent color-coded badges and dots throughout.
- **Countdown timers:** Prominent, slightly urgent styling for approaching auto-select deadlines (turns amber at 30min, red at 10min).
- **Charts:** Use Recharts with the teal/navy palette. Clean axes, subtle gridlines.
- **Empty states:** Friendly messages with icons and CTAs.
- **Mobile responsive:** Sidebar collapses to hamburger. Content queue stacks vertically. Calendar shows day view on mobile.
- **Dark mode:** Not required for MVP.

---

## ENVIRONMENT VARIABLES

### Backend (.env)
```
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tg_content_engine

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Encryption
ENCRYPTION_KEY=your-fernet-key-here

# External APIs
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
# OR: TOGETHER_API_KEY=... (if using Together AI for Nano Banana Pro)

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHANNEL_ID=@idigov_channel  # or -100xxxxxxxxxx
TELEGRAM_SMM_CHAT_ID=123456789  # SMM specialist's personal chat ID for notifications

# Timezone
APP_TIMEZONE=Asia/Dubai

# Scraping
SCRAPE_USER_AGENT=Mozilla/5.0 (compatible; IDIGOVBot/1.0)
SCRAPE_REQUEST_DELAY_SEC=2  # Polite delay between requests
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

---

## IMPLEMENTATION ORDER

Build the project in this exact order. Each phase should be fully working before moving to the next.

### Phase 1: Foundation
1. Initialize the Next.js frontend project with TypeScript, Tailwind CSS, shadcn/ui
2. Initialize the FastAPI backend project with SQLAlchemy, Alembic
3. Set up docker-compose.yml with PostgreSQL + Redis containers
4. Create all SQLAlchemy models and run initial Alembic migration
5. Implement auth: registration, login, JWT tokens, role middleware
6. Build the login page on frontend
7. Build the dashboard layout (sidebar + header + breadcrumb)
8. Implement the API client in frontend with auth interceptor
9. Create database seed script (default admin user, default scrape sources, default templates)

### Phase 2: Scraping Engine
1. Build the base scraper service with httpx + trafilatura
2. Build RSS scraper
3. Build website scraper with CSS selector support
4. Build relevance scoring service (Claude API)
5. Build scrape source CRUD API endpoints
6. Build scrape run management API
7. Build the Scraper Dashboard page (status overview + run history)
8. Build the Scraper Sources management page
9. Set up Celery + Redis, create the scheduled scraping task
10. Test: sources get scraped, articles get scored and stored

### Phase 3: Content Generation
1. Build the content generator service (Claude API integration)
2. Build the image generator service (Nano Banana Pro / Gemini API integration)
3. Build the market analyzer service (Claude API with data)
4. Build the content slot creation logic (5 daily slots)
5. Build the generate_all_slots Celery task
6. Build the ContentSlot and PostOption API endpoints
7. Build the Content Queue page (main SMM view with option cards)
8. Build the Content Slot Detail page (side-by-side comparison + editor)
9. Build the Telegram-style post preview component
10. Test: scrape → generate → review flow end-to-end

### Phase 4: Publishing Pipeline
1. Build the Telegram publisher service (python-telegram-bot)
2. Build the auto-selector service (Claude API evaluation)
3. Build the auto_select_if_needed Celery task
4. Build the publish_slot Celery task
5. Build the slot selection API (SMM picks option A/B)
6. Build the post editing flow (SMM edits before selecting)
7. Build countdown timer component for approval deadlines
8. Build SMM notification service (Telegram DM)
9. Set up full Celery Beat schedule
10. Test: full daily cycle — scrape → generate → approve/auto-select → publish

### Phase 5: Analytics & History
1. Build the Telegram analytics collector service
2. Build the analytics update Celery task
3. Build the channel snapshot task
4. Build all Analytics API endpoints
5. Build the Analytics Dashboard page (charts + KPIs)
6. Build the Published Posts list and detail pages
7. Build the Content Calendar page
8. Build the Dashboard stats and today's schedule components

### Phase 6: Configuration & Polish
1. Build the Templates CRUD API and management page
2. Build the Settings API with encryption
3. Build the Settings page (all tabs)
4. Build User management (admin)
5. Add error boundaries and error pages
6. Add loading skeletons for all pages
7. Add empty states for all lists
8. Add toast notifications (Sonner) for all actions
9. Add role-based UI visibility
10. Test all flows end-to-end
11. Write README with setup instructions

---

## IMPORTANT DEVELOPMENT NOTES

1. **Always use async:** Both FastAPI and SQLAlchemy should use async patterns.
2. **Dubai timezone:** All scheduling logic must be timezone-aware. Store datetimes in UTC, display in Asia/Dubai. Use `date-fns-tz` on frontend and `zoneinfo` on backend.
3. **Pagination:** All list endpoints support `?page=1&per_page=20` with total count in response.
4. **Error handling:** Every API endpoint has try/except with proper HTTP status codes.
5. **CORS:** Configure FastAPI CORS for frontend origin.
6. **Polite scraping:** Respect robots.txt, use delays between requests, rotate user agents. Never DDoS sources.
7. **Deduplication:** Articles must be deduped by URL and by title similarity before storing.
8. **Telegram rate limits:** Respect Telegram Bot API rate limits (max 30 messages/second to same chat, but we're only posting 5/day so this isn't a concern — mainly relevant for analytics polling).
9. **Image storage:** Store generated images locally on the server (in a media/ directory) and serve them for preview. Upload to Telegram directly from the file.
10. **Content quality:** The Claude prompts should emphasize factual accuracy, source attribution, and engagement. Never fabricate data.
11. **Graceful degradation:** If scraping fails, use cached articles. If Nano Banana Pro image generation fails, publish text-only. If auto-select fails, send urgent notification to SMM.
12. **Seeds:** Create a seed script with: default admin user (admin@idigov.com / changeme), all scrape sources from the table above, default post templates for each category.
13. **Post language strategy:** Default to posting in the channel's primary language. If "both" is configured, post EN version first, then RU as a separate message (not a reply, to avoid clutter).

---

## DEFAULT POST TEMPLATES TO SEED

### Real Estate News
```
You are the content writer for IDIGOV Real Estate's Telegram channel.

Based on the following real estate news:
{articles}

Write an engaging Telegram post. Requirements:
- Hook line with a surprising fact or number
- 2-3 short paragraphs covering the key points
- Mention the source of the data/news
- Relate to Dubai real estate investors and residents
- Subtle IDIGOV positioning (as a knowledgeable agency)
- 800-1500 characters total
- Write in BOTH English and Russian
- Include 3-5 hashtags

JSON response format:
{"title_en": "...", "body_en": "...", "title_ru": "...", "body_ru": "...", "hashtags": [...], "image_prompt": "...", "content_type": "news"}
```

### Market Analysis / Prediction
```
You are an expert real estate market analyst writing for IDIGOV's Telegram channel.

Based on the following market data:
{market_data}

And supporting articles:
{articles}

Write a data-driven analysis post. Requirements:
- Lead with the most striking data point
- Include specific numbers (prices, percentages, transaction volumes)
- Make a clear, data-backed prediction or insight
- Always cite the data source (e.g., "According to DLD data...")
- Make it exciting but credible — not hype, not boring
- 800-1500 characters total
- Write in BOTH English and Russian
- Include 3-5 hashtags

JSON response format:
{"title_en": "...", "body_en": "...", "title_ru": "...", "body_ru": "...", "hashtags": [...], "image_prompt": "...", "content_type": "market_analysis|prediction"}
```

### Dubai General / Lifestyle / Trending
```
You are the content writer for IDIGOV Real Estate's Telegram channel.

Based on the following Dubai/UAE news:
{articles}

Write an engaging Telegram post about what's happening in Dubai. This can be about 
ANYTHING trending — events, new restaurant openings, sports, viral moments, tourism 
milestones, transportation updates, cultural happenings, technology, entertainment, 
celebrity visits, record-breaking achievements, new laws, or anything else interesting.

Requirements:
- Pick the angle that would generate the most interest/engagement
- Match the tone to the topic (exciting for events, practical for transport/rules, 
  impressive for records/achievements, fun for lifestyle/food)
- Make it feel timely — this is happening NOW in Dubai
- Connect it (subtly) to why Dubai is a great place to live/invest
- 800-1500 characters total
- Write in BOTH English and Russian
- Include 3-5 hashtags

JSON response format:
{"title_en": "...", "body_en": "...", "title_ru": "...", "body_ru": "...", "hashtags": [...], "image_prompt": "...", "content_type": "lifestyle|events|tourism|food_dining|sports|transportation|culture|entertainment|tech|regulation|construction|health|environment|government|business|general"}
```

---

## TELEGRAM ANALYTICS — WHAT'S RETRIEVABLE

Based on research into the Telegram Bot API and MTProto API, here is exactly what metrics are available programmatically and how the system should collect them:

### Via Bot API (what our bot can access as channel admin)

| Metric | Method | Notes |
|--------|--------|-------|
| **Views per post** | `Message.views` field on forwarded/channel messages | Available on every message object. **Approximate** for messages >7 days old (Telegram switches to sampled aggregation). For accuracy, capture views within the first 48 hours. |
| **Forwards per post** | `Message.forward_count` field | Available directly on message objects |
| **Reaction counts (anonymous)** | `message_reaction_count` update | For channel posts, only aggregate counts per emoji are available (e.g., 👍: 12, ❤️: 5). Individual user reactions are NOT visible for channels. Bot must be admin and include `message_reaction_count` in `allowed_updates`. |
| **Reply count** | Count replies in linked discussion group | Only works if channel has a linked discussion group. Bot monitors the group for messages with `reply_to_message` pointing to the channel post. |
| **Subscriber count** | `getChat` → `ChatFullInfo.member_count` | Returns current subscriber count. Call daily for growth tracking. |

### Via Telegram MTProto API (more data, requires user account session)

| Metric | Method | Notes |
|--------|--------|-------|
| **Full channel statistics** | `stats.getBroadcastStats` | Returns: followers, views_per_post, shares_per_post, reactions_per_post, growth graph, enabled notifications %, subscriber source breakdown, top hours, language breakdown. **Requires 50+ subscribers and admin access.** |
| **Per-message detailed stats** | `stats.getMessageStats` | Returns views graph over time for a specific message. |
| **Message view counts** | `messages.getMessagesViews` | Batch-fetch view counts for multiple message IDs at once. |

### Recommended Analytics Strategy

```python
"""
analytics_collector.py — Dual-mode analytics collection

PRIMARY MODE (Bot API — simpler, recommended for MVP):
1. After publishing a post, store the telegram_message_id
2. Every hour for 48 hours: 
   - Call getChat to get subscriber count
   - Forward the message to the bot's own private chat to refresh view count
   - Read Message.views and Message.forward_count from the forwarded message
   - Listen for message_reaction_count updates via webhook
3. Store hourly snapshots in post_analytics.hourly_snapshots
4. Calculate engagement_rate = (forwards + reactions_total) / views * 100

ADVANCED MODE (MTProto — more data, optional Phase 2):
If richer analytics are needed later, integrate Telethon or Pyrogram 
(Python MTProto clients) using a dedicated user account session to access 
stats.getBroadcastStats and stats.getMessageStats. This provides:
  - Subscriber source breakdown (search, forwards, other channels)
  - Notification enable rate
  - Detailed views-over-time graphs per message
  - Language/geography breakdown

LIMITATION NOTES:
- Bot API cannot call getChatStatistics (channel stats page) — that's MTProto only
- View counts become approximate after ~7 days — persist raw counts early
- Reaction details for channels are anonymous (counts only, no user attribution)
- Subscriber count via getChat is real-time but doesn't show historical growth
  (must be stored daily to calculate growth curves)
"""
```

### What the Analytics Dashboard Can Show (with Bot API only)

| Metric | Source | Accuracy |
|--------|--------|----------|
| Views per post | Message.views | ✅ Accurate (first 48h), approximate after |
| Forwards per post | Message.forward_count | ✅ Accurate |
| Reactions per post (emoji breakdown) | message_reaction_count update | ✅ Accurate counts, anonymous |
| Engagement rate | Computed | ✅ Reliable |
| Subscriber count & daily growth | getChat daily | ✅ Accurate |
| Views over time (hourly graph) | Hourly snapshots | ✅ Accurate (our own collection) |
| Subscriber source breakdown | ❌ Not available via Bot API | Requires MTProto |
| Notification enable rate | ❌ Not available via Bot API | Requires MTProto |
| Geographic/language breakdown | ❌ Not available via Bot API | Requires MTProto |

**Verdict:** Bot API is sufficient for a comprehensive analytics dashboard covering all the essential KPIs (views, engagement, growth, top posts, category performance, time heatmaps). The MTProto integration can be added in a later phase if deeper subscriber insights are needed.

---

## SCRAPING SOURCE PAYMENT ANALYSIS

Analysis of all listed scraping sources to determine which are free and which may require payment or have access restrictions:

### ✅ FREE — No Payment Required

| Source | Type | Access Notes |
|--------|------|-------------|
| **Gulf News** (all sections) | RSS | Free RSS feeds available. Website scraping also works. Rate limit: be polite. |
| **Khaleej Times** (all sections) | RSS/Website | Free RSS. Website has no paywall for most articles. |
| **WAM (Emirates News Agency)** | Website | Fully free. Government news agency, public data. |
| **Dubai Media Office** | Website | Fully free. Official government press releases. |
| **Property Finder Blog** | Website | Free blog content. Not behind paywall. |
| **Bayut Blog (MyBayut)** | Website | Free blog content. Not behind paywall. |
| **Time Out Dubai** | Website | Free. May have soft ad-walls but content is accessible. |
| **What's On Dubai** | Website | Free. Content accessible without subscription. |
| **Lovin Dubai** | Website | Free. Viral/social content, fully accessible. |
| **Visit Dubai Blog** | Website | Free. Tourism authority content. |
| **Dubai Calendar** | Website | Free. Government events platform. |
| **CBUAE (Central Bank)** | Website | Free. Government public data. |
| **Dubai Economy & Tourism** | Website | Free. Government portal. |
| **RTA News** | Website | Free. Government transport authority. |
| **Construction Week Online** | Website | Free. May require registration for some content. |
| **Sport360** | Website | Free sports news. |
| **Reddit r/dubai** | Website/API | Free. Reddit API has rate limits but is accessible for small-scale scraping. Reddit's robots.txt allows scraping of public pages. |
| **Google News** | RSS | Free via Google News RSS feeds (unlimited). Format: `https://news.google.com/rss/search?q=Dubai+{topic}` |
| **DXB Interact** | Website | Free. 100% free property data platform (backed by fäm Properties, sourced from DLD). No API but website data is publicly accessible. |
| **Dubai Land Department Open Data** | Website | Free. Government open data portal. |
| **Gulf Business Tech** | Website | Free. |
| **ITP.net** | Website | Free. |

### Recommended Approach

1. **All sources are free (no paid subscriptions needed).** The 20+ free sources listed above provide more than enough material for 5 daily posts.

2. **DXB Interact for market data (Free):** Scrape DXB Interact's publicly available data (transaction trends, price per sqft, area comparisons) for market analysis posts. This is free and sourced from DLD.

3. **Google News as a catch-all:** Use Google News RSS feeds (free, unlimited) to catch trending stories from ANY source. Format: `https://news.google.com/rss/search?q=Dubai+{topic}&hl=en&gl=AE&ceid=AE:en`. This ensures you never miss a viral story regardless of source.

4. **DLD API for licensed RE companies:** Since IDIGOV is a registered real estate company, you likely qualify for free access to the Rental Index API and Brokers API. Apply through the DLD API Gateway portal.

**Estimated Total Scraping Cost: $0/month**

---

- **Backend:** `pytest` + `httpx.AsyncClient`. Mock Claude API, Nano Banana Pro API, and Telegram Bot in tests.
- **Scraping tests:** Mock HTTP responses for each source type. Test deduplication and relevance scoring.
- **Manual testing checklist:**
  1. Login as admin → see all pages
  2. Login as SMM → see content queue, analytics, posts (no settings/sources)
  3. Login as viewer → dashboard + analytics only
  4. Scraper runs → articles appear in scraper dashboard
  5. Content generates → 2 options per slot visible in content queue (10 options total for 5 slots)
  6. SMM selects option → post publishes to Telegram
  7. No selection → AI auto-selects after deadline → post publishes
  8. Edit option content → modified version publishes correctly
  9. Skip a slot → no post published, slot marked skipped
  10. Analytics update → post metrics visible in analytics dashboard
  11. Calendar shows correct status colors for past, present, future slots
  12. Add new scrape source → test scrape returns articles
  13. Modify template → new content uses updated template

---

This document serves as the complete specification. Build each phase incrementally, commit often, and test each feature before moving to the next. When in doubt about a UI decision, prefer simplicity and clarity — this is a tool for a non-technical SMM specialist who needs to make quick decisions.
