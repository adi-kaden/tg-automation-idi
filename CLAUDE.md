# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TG Content Engine** is an internal automation platform for IDIGOV Real Estate (Dubai) that automates Telegram channel content production and publishing. The system scrapes Dubai/UAE news and market data, generates AI-written bilingual posts (EN/RU) with images, presents options to an SMM specialist for approval, and auto-publishes on a fixed schedule.

## Tech Stack

### Frontend
- **Next.js 15** (App Router) + TypeScript
- **Tailwind CSS 4** + **shadcn/ui**
- **TanStack Query v5** for data fetching
- **Zustand** for state management
- **React Hook Form** + **Zod** for forms
- **Recharts** for analytics charts
- **Tiptap** for rich text editing
- **date-fns** + **date-fns-tz** for Dubai timezone handling

### Backend
- **FastAPI** (Python 3.12+)
- **Celery** + **Redis** for task queue and scheduling
- **SQLAlchemy 2.0** (async) + **Alembic** migrations
- **Pydantic v2** for validation
- **httpx** + **BeautifulSoup4** + **trafilatura** for scraping
- **python-telegram-bot v21+** for Telegram integration

### Database
- **PostgreSQL 16** (Supabase)
- **Redis 7** (cache/broker)

### External APIs
- **Claude API** (Anthropic) - content generation, analysis, auto-selection
- **Gemini 3 Pro Image** (Nano Banana Pro) - image generation
- **Telegram Bot API** - publishing + analytics

## Project Structure

```
tg-content-engine/
├── frontend/                 # Next.js app
│   └── src/
│       ├── app/              # App Router pages
│       │   ├── (auth)/       # Login pages
│       │   └── (dashboard)/  # Main app pages
│       ├── components/       # React components by feature
│       ├── lib/              # API client, utils, constants
│       ├── hooks/            # Custom React hooks
│       ├── stores/           # Zustand stores
│       └── types/            # TypeScript types
├── backend/                  # FastAPI app
│   └── app/
│       ├── main.py           # Entry point
│       ├── config.py         # Pydantic settings
│       ├── database.py       # SQLAlchemy async engine
│       ├── models/           # SQLAlchemy ORM models
│       ├── schemas/          # Pydantic request/response
│       ├── api/              # Route handlers
│       ├── services/         # Business logic + external APIs
│       │   └── scraper/      # Scraper implementations
│       ├── tasks/            # Celery async tasks
│       └── utils/            # Helpers (security, timezone, etc.)
│   └── alembic/              # Database migrations
└── docker-compose.yml        # Local dev: PostgreSQL + Redis
```

## Development Commands

### Frontend
```bash
cd frontend
npm install                   # Install dependencies
npm run dev                   # Start dev server (http://localhost:3000)
npm run build                 # Production build
npm run lint                  # Run ESLint
npx shadcn@latest add <name>  # Add shadcn component
```

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # Start dev server (http://localhost:8000)
pytest                                  # Run tests
pytest tests/test_scraper.py -v        # Run single test file
alembic upgrade head                    # Run migrations
alembic revision --autogenerate -m "msg" # Create migration
```

### Celery
```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info   # Start worker
celery -A app.tasks.celery_app beat --loglevel=info     # Start scheduler
```

### Docker (Local Dev)
```bash
docker-compose up -d          # Start PostgreSQL + Redis
docker-compose down           # Stop containers
```

## Architecture Notes

### Daily Posting Schedule (Dubai Time, GMT+4)
| Slot | Time | Type |
|------|------|------|
| 1 | 08:00 | Real Estate |
| 2 | 12:00 | Dubai Trending |
| 3 | 16:00 | Real Estate |
| 4 | 20:00 | Dubai Trending |
| 5 | 00:00 | Dubai Trending |

### Content Pipeline Flow
1. **04:00** - Scrape all sources
2. **05:00** - Generate 2 options per slot (10 total posts)
3. **30 min before each slot** - Auto-select if no human selection
4. **At slot time** - Publish to Telegram

### Key Services
- `content_generator.py` - Claude API for post writing
- `image_generator.py` - Gemini/Nano Banana Pro for images
- `auto_selector.py` - Claude API for choosing best option
- `telegram_publisher.py` - Telegram Bot API for publishing
- `analytics_collector.py` - Telegram metrics collection

### Timezone Handling
- All datetimes stored in UTC
- Display in Asia/Dubai (GMT+4)
- Use `zoneinfo` on backend, `date-fns-tz` on frontend

## Database Models

Core entities: `User`, `ScrapeSource`, `ScrapeRun`, `ScrapedArticle`, `ContentSlot`, `PostOption`, `PublishedPost`, `PostAnalytics`, `ChannelSnapshot`, `PostTemplate`, `Setting`

All tables use UUID primary keys and `created_at`/`updated_at` timestamps.

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tg_content_engine
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=@channel_name
APP_TIMEZONE=Asia/Dubai
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## Implementation Phases

1. **Foundation** - Project setup, auth, database models
2. **Scraping Engine** - Source management, scheduled scraping
3. **Content Generation** - Claude + Gemini integration, slot creation
4. **Publishing Pipeline** - Auto-selection, Telegram publishing
5. **Analytics & History** - Metrics collection, dashboards
6. **Configuration & Polish** - Templates, settings, error handling

## Task Master Integration

This project uses Task Master for workflow management:
```bash
task-master list              # View all tasks
task-master next              # Get next available task
task-master show <id>         # View task details
task-master set-status --id=<id> --status=done
```

Reference `.taskmaster/CLAUDE.md` for full command reference.
