# SPEC: Real Published Posts Data + Live Analytics

## Problem

The published posts page displays hardcoded mock data. No backend endpoint exists for listing published posts. The analytics collector returns zeros because the Telegram Bot API cannot access channel post metrics (views, reactions, forwards). The dashboard analytics are also empty.

## Solution

Replace the entire published posts data pipeline with real Telegram data using Telethon (MTProto API), create the missing backend endpoints, and rebuild the frontend with a paginated table and detail drawer.

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Analytics API | Telethon (MTProto) | Bot API cannot access channel message views/reactions |
| Session storage | StringSession in env var | Railway (PaaS) has no persistent filesystem |
| Polling frequency | Every 5 min via Celery Beat | Matches Telegram stats update cadence |
| Polling scope | Last 7 days of posts | ~35 posts max, single batch API call |
| Backfill | None — forward only | Simplicity; old posts have minimal analytics value |
| Frontend updates | React Query polling every 5 min | Matches backend collection frequency |
| Page UX | Paginated table + detail drawer | Scalable for growing post count |

## Channel

- Public channel: **@idigovnews**
- Post links: `https://t.me/idigovnews/{telegram_message_id}`

## Backend Changes

### 1. Telethon Integration

**New env vars:**
```
TELEGRAM_API_ID=<from my.telegram.org>
TELEGRAM_API_HASH=<from my.telegram.org>
TELEGRAM_SESSION_STRING=<output from one-time auth script>
```

**New dependency:** `telethon==1.37.0`

**One-time auth script** (`backend/scripts/generate_telethon_session.py`):
- Run locally, prompts for phone + OTP
- Outputs StringSession string to copy into Railway env vars
- Never runs in production

### 2. Analytics Collector Rewrite

**File:** `backend/app/services/analytics_collector.py`

Replace `get_post_stats()` (returns zeros) with Telethon batch fetch:
```python
messages = await client.get_messages(channel_entity, ids=message_ids)
```

Each `Message` object provides:
- `message.views` — view count
- `message.forwards` — forward count
- `message.replies.replies` — reply count (null-check required)
- `message.reactions.results` — list of `{emoji, count}` (null-check required)

**Lifecycle:** `connect()` / `disconnect()` methods. Client created inside async task context (not module-level) to avoid Celery event loop conflicts.

**Error handling:**
- `FloodWaitError` — sleep for `e.seconds`, retry once
- `AuthKeyUnregisteredError` — log error, return zeros, don't crash worker

### 3. New API Endpoints

**Router:** `backend/app/api/published_posts.py` mounted at `/published-posts`

#### `GET /published-posts`

Paginated list of published posts with analytics.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page (max 100) |
| content_type | string | null | Filter: "real_estate" or "general_dubai" |
| language | string | null | Filter: "en" or "ru" |
| date_from | date | null | Filter: published after |
| date_to | date | null | Filter: published before |
| sort_by | string | "published_at" | Sort field: published_at, views, engagement_rate, forwards |
| sort_order | string | "desc" | Sort direction: asc, desc |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "slot_id": "uuid",
      "option_id": "uuid",
      "posted_title": "...",
      "posted_body": "...",
      "posted_language": "ru",
      "posted_image_url": null,
      "telegram_message_id": 123,
      "telegram_channel_id": "@idigovnews",
      "selected_by": "human",
      "published_at": "2026-03-09T08:00:00Z",
      "content_type": "real_estate",
      "telegram_link": "https://t.me/idigovnews/123",
      "image_url_served": "/api/published-posts/uuid/image",
      "analytics": {
        "views": 2450,
        "forwards": 45,
        "replies": 23,
        "reactions": {"👍": 100, "❤️": 30, "🔥": 26},
        "engagement_rate": 8.94,
        "view_growth_1h": 5.2,
        "view_growth_24h": 120.5,
        "last_fetched_at": "2026-03-09T12:05:00Z"
      }
    }
  ],
  "total": 45,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

**Implementation:**
- LEFT OUTER JOIN `PublishedPost` ↔ `PostAnalytics` (posts without analytics still appear)
- JOIN `ContentSlot` for `content_type`
- Compute `telegram_link` and `image_url_served` in response serialization

#### `GET /published-posts/{id}`

Single post with full analytics. Same response shape as list item.

#### `GET /published-posts/{id}/image`

Serves the post's image.

- Looks up `PostOption` via `PublishedPost.option_id`
- If `PostOption.image_data` exists: decode base64, return as `image/png`
- If `PostOption.image_url` exists: redirect (302)
- Otherwise: 404
- **Unauthenticated** (images are already public on Telegram)

### 4. Dashboard Fix

**File:** `backend/app/api/dashboard.py`

Fix line 316: `content_type=post.posted_language` → use `slot.content_type` via eager-loaded relationship.

### 5. Celery Beat Schedule

**File:** `backend/app/tasks/celery_app.py`

```python
# Before:
"collect-post-analytics": {
    "schedule": crontab(hour="*/6", minute=15),
    "kwargs": {"hours_back": 48},
}

# After:
"collect-post-analytics": {
    "schedule": crontab(minute="*/5"),
    "kwargs": {"days_back": 7},
}
```

**Task update** (`analytics_tasks.py`):
- Initialize Telethon client inside async context
- `connect()` / `disconnect()` in try/finally
- Handle `FloodWaitError` with `self.retry(countdown=e.seconds + 5)`

## Frontend Changes

### 1. Posts Page Rewrite

**File:** `frontend/src/app/(dashboard)/posts/page.tsx`

Replace mock data with real API calls.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│ Published Posts                          45 total    │
├─────────────────────────────────────────────────────┤
│ [Search...] [All] [Real Estate] [Trending] [Dates]  │
├────────┬──────────┬──────┬───────┬────┬─────┬───────┤
│ Date ↕ │ Title    │ Type │ Views │ ↕  │ Eng │ Link  │
├────────┼──────────┼──────┼───────┼────┼─────┼───────┤
│ Mar 9  │ Dubai... │ RE   │ 2450  │ 45 │ 8.9%│  ↗    │
│ Mar 9  │ New...   │ TR   │ 3200  │ 89 │ 12% │  ↗    │
│ ...    │          │      │       │    │     │       │
├────────┴──────────┴──────┴───────┴────┴─────┴───────┤
│ ← Previous    Page 1 of 3    Next →                  │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Sortable columns: Date, Views, Engagement
- Filter by content type (buttons), date range (calendar picker)
- Search (client-side on loaded page data)
- Pagination (server-side)
- Click row → opens detail drawer
- React Query: `refetchInterval: 300000` (5 min)

### 2. Post Detail Drawer

**File:** `frontend/src/components/posts/post-detail-drawer.tsx`

Uses shadcn `Sheet` component (already installed).

**Layout:**
```
┌─────────────────────────────┐
│ Post Details            [X] │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │       Post Image        │ │
│ └─────────────────────────┘ │
│                             │
│ Post Title Here             │
│ [Real Estate] [RU]          │
│ Mar 9, 2026 08:00 Dubai     │
│ Selected by: Human          │
│                             │
│ Full post body text here... │
│                             │
│ ── Analytics ────────────── │
│ 👁 2,450  ↗ 45  💬 23      │
│                             │
│ Reactions:                  │
│ 👍 100  ❤️ 30  🔥 26       │
│                             │
│ Engagement: 8.94%           │
│ Growth 1h: +5.2%            │
│ Growth 24h: +120.5%         │
│                             │
│ Updated: 12:05 PM           │
│                             │
│ [View on Telegram ↗]        │
└─────────────────────────────┘
```

### 3. API Client & Hooks Updates

**`frontend/src/lib/api.ts`**: Add `sort_by`, `sort_order`, `date_from`, `date_to` params to `publishedPosts.list`.

**`frontend/src/hooks/use-api.ts`**: Add `refetchInterval: 300000` to `usePublishedPosts` and `usePublishedPost`.

**`frontend/src/types/index.ts`**: Add `PublishedPostDetail` interface with `telegram_link`, `image_url_served`, `content_type`.

## Edge Cases

1. **Posts without analytics** — LEFT OUTER JOIN ensures they appear with null/zero stats
2. **Posts without images** — image endpoint returns 404, frontend shows placeholder
3. **Posts without telegram_message_id** — no Telegram link shown, analytics not collected
4. **Telethon session expires** — `AuthKeyUnregisteredError` caught, zeros returned, error logged
5. **FloodWait** — Celery task retries after wait period
6. **Reactions field is JSON string in DB** — parsed to dict before API response
7. **`message.reactions` or `message.replies` is None** — null-checked before access

## Deployment Steps

1. Add `telethon` to `requirements.txt`, deploy backend
2. Run `python scripts/generate_telethon_session.py` locally (one-time)
3. Add `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING` to Railway
4. Redeploy backend
5. Deploy frontend
6. Wait 5 min, verify analytics populating

## Files Changed

| File | Action |
|------|--------|
| `backend/requirements.txt` | Modify — add telethon |
| `backend/app/config.py` | Modify — add 3 Telethon config fields |
| `backend/scripts/generate_telethon_session.py` | Create |
| `backend/app/services/analytics_collector.py` | Rewrite — Telethon MTProto |
| `backend/app/schemas/content.py` | Modify — add response schemas |
| `backend/app/api/published_posts.py` | Create — 3 endpoints |
| `backend/app/api/__init__.py` | Modify — register router |
| `backend/app/api/dashboard.py` | Modify — fix content_type |
| `backend/app/tasks/celery_app.py` | Modify — 5-min schedule |
| `backend/app/tasks/analytics_tasks.py` | Modify — Telethon lifecycle |
| `frontend/src/types/index.ts` | Modify — add PublishedPostDetail |
| `frontend/src/lib/api.ts` | Modify — extend params |
| `frontend/src/hooks/use-api.ts` | Modify — add refetchInterval |
| `frontend/src/app/(dashboard)/posts/page.tsx` | Rewrite |
| `frontend/src/components/posts/post-detail-drawer.tsx` | Create |
| `backend/scripts/test_telethon_connection.py` | Create |

---

# SPEC: Enforce 2-Day Article Age Limit

## Problem

Scraped articles with `published_at` dates months or years old appear on the scraped articles page (e.g., under Economy filters). The current cleanup only deletes based on `scraped_at` (when we scraped it), so an article published 6 months ago but scraped today survives cleanup for 2 days and pollutes the content pool.

## Solution

Reject articles older than 2 days **at scrape time** based on their `published_at` date. Add a rejected URLs tracking table to prevent re-processing. Enhance the existing cleanup task for defense-in-depth.

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Enforcement point | At scrape time | Old articles never touch the DB. Simplest and most efficient. |
| NULL `published_at` | Allow through | Can't determine age — rely on `scraped_at` cleanup. Won't lose valid articles. |
| Rejected URL tracking | Yes, dedicated table | Prevents re-fetching old articles that persist in RSS feeds every cycle. |
| Rejected URL expiry | 30 days | Covers most feed rotation cycles. Keeps table small. |
| Cleanup enhancement | Dual: `scraped_at` OR `published_at` | Defense-in-depth catches edge cases. |
| One-time purge | Yes, in migration | Clean slate immediately on deploy. |
| Age limit config | Hardcoded constant | Unlikely to change. Simple. |
| Timezone handling | Normalize to UTC | Avoids ~12h error from inconsistent source timezones. |
| Rejected URL cleanup | Same daily task | No new Celery Beat entry. Piggybacks on existing 03:00 schedule. |
| Frontend changes | None | Old articles simply won't exist in the DB. |

---

## 1. Scrape-Time Rejection

### Location
`backend/app/tasks/scraper_tasks.py` — `_save_article()` function (around line 225)

### Logic
Before saving a new article, check its `published_at`:

```python
MAX_ARTICLE_AGE_DAYS = 2  # Define in backend/app/config.py

# In _save_article(), after deduplication check:
if item.published_at is not None:
    published_at_utc = normalize_to_utc(item.published_at)
    cutoff = datetime.utcnow() - timedelta(days=MAX_ARTICLE_AGE_DAYS)
    if published_at_utc < cutoff:
        # Save URL to rejected table, skip article
        await _save_rejected_url(session, item.url, reason="too_old")
        logger.info(f"Rejected old article ({item.published_at}): {item.url}")
        return False
```

### NULL `published_at` Handling
- Articles with **NULL** `published_at` are **allowed through** — we can't determine their age, so we rely on `scraped_at`-based cleanup for those.

### Timezone Normalization
Add a `normalize_to_utc()` helper that:
1. If datetime is timezone-aware → convert to UTC, strip tzinfo
2. If datetime is naive → assume UTC (current behavior)

---

## 2. Rejected URLs Table

### Model: `RejectedArticleURL`
**Location:** `backend/app/models/rejected_url.py`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `url` | String(2000) | Unique, indexed |
| `reason` | String(50) | e.g., "too_old" |
| `rejected_at` | DateTime | When it was rejected |
| `expires_at` | DateTime | `rejected_at + 30 days` |

### Purpose
- Prevent re-fetching and re-evaluating old articles that persist in RSS feeds
- Entries expire after **30 days** — the URL is forgotten and can be re-evaluated if it reappears

### Integration with Scraper
In `_save_article()`, check rejected URLs table **before** the existing URL deduplication check:

```python
# Check if URL was previously rejected (and not expired)
rejected = await session.execute(
    select(RejectedArticleURL).where(
        RejectedArticleURL.url == item.url,
        RejectedArticleURL.expires_at > datetime.utcnow()
    )
)
if rejected.scalar_one_or_none():
    return False  # Skip silently
```

### Alembic Migration
Create a new migration for the `rejected_article_urls` table.

---

## 3. Enhanced Cleanup Task

### Location
`backend/app/tasks/scraper_tasks.py` — `cleanup_old_articles()`

### Changes

**A. Dual cleanup on ScrapedArticle:**
Delete articles where EITHER condition is true:
- `scraped_at < cutoff` (existing behavior)
- `published_at IS NOT NULL AND published_at < cutoff` (new)

```python
cutoff = datetime.utcnow() - timedelta(days=days_old)

# Clear FK references first (existing logic, extended with OR)
# Then delete where scraped_at is old OR published_at is old
delete_query = delete(ScrapedArticle).where(
    or_(
        ScrapedArticle.scraped_at < cutoff,
        and_(
            ScrapedArticle.published_at.isnot(None),
            ScrapedArticle.published_at < cutoff
        )
    )
)
```

**B. Prune expired rejected URLs** (same task):
```python
# Clean up expired rejected URL entries
await session.execute(
    delete(RejectedArticleURL).where(
        RejectedArticleURL.expires_at < datetime.utcnow()
    )
)
```

No new Celery Beat entry needed — piggybacks on the existing daily 03:00 Dubai schedule.

---

## 4. One-Time Migration Purge

### Purpose
Remove all existing articles in the DB that have `published_at` older than 2 days. Clean slate on deploy.

### Implementation
Add to the Alembic migration that creates `rejected_article_urls`:

```python
def upgrade():
    # Create rejected_article_urls table
    op.create_table(...)

    # One-time purge: clear FK references first, then delete
    cutoff = (datetime.utcnow() - timedelta(days=2)).isoformat()
    op.execute(
        f"UPDATE scraped_articles SET used_in_post_id = NULL, is_used = FALSE "
        f"WHERE published_at IS NOT NULL AND published_at < '{cutoff}'"
    )
    op.execute(
        f"DELETE FROM scraped_articles "
        f"WHERE published_at IS NOT NULL AND published_at < '{cutoff}'"
    )
```

---

## 5. Debug Endpoint Update

### Location
`backend/app/main.py` — `POST /debug/cleanup-old-articles`

Update to use the same dual cleanup logic (both `scraped_at` and `published_at`).

---

## 6. Config Constants

### Location
`backend/app/config.py`

```python
MAX_ARTICLE_AGE_DAYS: int = 2
REJECTED_URL_EXPIRY_DAYS: int = 30
```

Hardcoded — not configurable via UI.

---

## Files to Modify

| File | Action |
|------|--------|
| `backend/app/config.py` | Modify — add `MAX_ARTICLE_AGE_DAYS`, `REJECTED_URL_EXPIRY_DAYS` |
| `backend/app/models/rejected_url.py` | **Create** — `RejectedArticleURL` model |
| `backend/app/models/__init__.py` | Modify — export new model |
| `backend/app/tasks/scraper_tasks.py` | Modify — age check in `_save_article()`, rejected URL check, dual cleanup |
| `backend/app/main.py` | Modify — update debug cleanup endpoint |
| `alembic/versions/xxx_add_rejected_urls.py` | **Create** — new table + one-time purge |

## Files NOT Modified

- **Frontend** — no UI changes; old articles simply won't exist in the DB
- **Content generation / auto-selector** — no changes; they pick from whatever's in the DB
- **Celery beat schedule** — no new entries; rejected URL cleanup piggybacks on existing task

---

## Verification

1. **Unit test**: Article with `published_at` = 5 days ago → `_save_article()` returns False, URL in rejected table
2. **Unit test**: Article with `published_at` = 1 day ago → saved normally
3. **Unit test**: Article with `published_at` = None → saved normally
4. **Unit test**: Previously-rejected URL → skipped on next scrape
5. **Integration test**: Cleanup task deletes articles with old `published_at` even if `scraped_at` is recent
6. **Manual**: After deploy, check scraped articles page Economy filter — no old articles
7. **Manual**: Trigger `/debug/cleanup-old-articles` → reports deleted count
8. **Manual**: Run scrape cycle → check logs for "Rejected old article" messages
