"""
Database seed script for TG Content Engine.
Creates default users, scrape sources, and post templates.
"""
import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import User, ScrapeSource, PostTemplate
from app.utils.security import hash_password


async def seed_users(db: AsyncSession):
    """Create default users."""
    users_data = [
        {
            "email": "admin@idigov.com",
            "name": "Admin User",
            "password": "Admin123!",
            "role": "admin",
        },
        {
            "email": "smm@idigov.com",
            "name": "SMM Specialist",
            "password": "Smm123!",
            "role": "smm",
        },
        {
            "email": "viewer@idigov.com",
            "name": "Viewer User",
            "password": "Viewer123!",
            "role": "viewer",
        },
    ]

    for user_data in users_data:
        # Check if user exists
        result = await db.execute(
            select(User).where(User.email == user_data["email"])
        )
        if result.scalar_one_or_none():
            print(f"  User {user_data['email']} already exists, skipping...")
            continue

        user = User(
            email=user_data["email"],
            name=user_data["name"],
            hashed_password=hash_password(user_data["password"]),
            role=user_data["role"],
        )
        db.add(user)
        print(f"  Created user: {user_data['email']}")

    await db.commit()


async def seed_scrape_sources(db: AsyncSession):
    """Create default scrape sources."""
    sources_data = [
        # ============ MOST RELIABLE - Google News RSS ============
        # These are the most reliable sources with 100+ articles each
        {
            "name": "Google News - Dubai Real Estate",
            "url": "https://news.google.com/rss/search?q=Dubai+real+estate&hl=en&gl=AE&ceid=AE:en",
            "source_type": "rss",
            "category": "real_estate",
            "language": "en",
        },
        {
            "name": "Google News - Dubai Property",
            "url": "https://news.google.com/rss/search?q=Dubai+property+market&hl=en&gl=AE&ceid=AE:en",
            "source_type": "rss",
            "category": "real_estate",
            "language": "en",
        },
        {
            "name": "Google News - Dubai",
            "url": "https://news.google.com/rss/search?q=Dubai&hl=en&gl=AE&ceid=AE:en",
            "source_type": "rss",
            "category": "general",
            "language": "en",
        },
        {
            "name": "Google News - UAE Economy",
            "url": "https://news.google.com/rss/search?q=UAE+economy&hl=en&gl=AE&ceid=AE:en",
            "source_type": "rss",
            "category": "economy",
            "language": "en",
        },
        {
            "name": "Google News - Dubai Construction",
            "url": "https://news.google.com/rss/search?q=Dubai+construction&hl=en&gl=AE&ceid=AE:en",
            "source_type": "rss",
            "category": "construction",
            "language": "en",
        },
        # ============ WORKING WEBSITES - Real Estate ============
        {
            "name": "Khaleej Times Property",
            "url": "https://www.khaleejtimes.com/property",
            "source_type": "website",
            "category": "real_estate",
            "language": "en",
        },
        {
            "name": "Property Finder Blog",
            "url": "https://www.propertyfinder.ae/blog/",
            "source_type": "website",
            "category": "real_estate",
            "language": "en",
        },
        {
            "name": "Bayut Blog",
            "url": "https://www.bayut.com/mybayut/",
            "source_type": "website",
            "category": "real_estate",
            "language": "en",
        },
        # ============ WORKING WEBSITES - Government/Official ============
        {
            "name": "WAM Emirates News Agency",
            "url": "https://www.wam.ae/en",
            "source_type": "website",
            "category": "government",
            "language": "en",
        },
        {
            "name": "Dubai Media Office",
            "url": "https://mediaoffice.ae/en/news",
            "source_type": "website",
            "category": "government",
            "language": "en",
        },
        # ============ WORKING WEBSITES - Lifestyle & Tourism ============
        {
            "name": "Visit Dubai",
            "url": "https://www.visitdubai.com/en/articles",
            "source_type": "website",
            "category": "tourism",
            "language": "en",
        },
        # ============ WORKING WEBSITES - Other Categories ============
        {
            "name": "Gulf Business Tech",
            "url": "https://gulfbusiness.com/category/technology/",
            "source_type": "website",
            "category": "tech",
            "language": "en",
        },
        {
            "name": "RTA News",
            "url": "https://www.rta.ae/wps/portal/rta/ae/home/news",
            "source_type": "website",
            "category": "transportation",
            "language": "en",
        },
        {
            "name": "Sport360",
            "url": "https://sport360.com/",
            "source_type": "website",
            "category": "sports",
            "language": "en",
        },
    ]

    # NOTE: The following sources were removed because they don't work:
    # - Gulf News RSS feeds (return 0 articles)
    # - Khaleej Times RSS (returns 0 articles)
    # - Time Out Dubai (403 Forbidden)
    # - Lovin Dubai (Connection error)
    # - Construction Week Online (403 Forbidden)
    # - DXB Interact (403 Forbidden)
    # - Dubai Calendar (unreliable)
    # - What's On Dubai (unreliable)
    # - CBUAE Central Bank (limited content)

    for source_data in sources_data:
        # Check if source exists
        result = await db.execute(
            select(ScrapeSource).where(ScrapeSource.url == source_data["url"])
        )
        if result.scalar_one_or_none():
            print(f"  Source {source_data['name']} already exists, skipping...")
            continue

        source = ScrapeSource(**source_data)
        db.add(source)
        print(f"  Created source: {source_data['name']}")

    await db.commit()


async def seed_templates(db: AsyncSession):
    """Create default post templates."""
    templates_data = [
        {
            "name": "Real Estate News",
            "category": "real_estate_news",
            "tone": "professional",
            "language": "both",
            "max_length_chars": 1500,
            "prompt_template": """You are the content writer for IDIGOV Real Estate's Telegram channel.

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
{"title_en": "...", "body_en": "...", "title_ru": "...", "body_ru": "...", "hashtags": [...], "image_prompt": "...", "content_type": "news"}""",
            "image_prompt_template": "Professional real estate photography of {subject} in Dubai, modern architecture, clean composition, no text overlays, photorealistic, 16:9 aspect ratio",
        },
        {
            "name": "Market Analysis",
            "category": "market_analysis",
            "tone": "analytical",
            "language": "both",
            "max_length_chars": 1500,
            "prompt_template": """You are an expert real estate market analyst writing for IDIGOV's Telegram channel.

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
{"title_en": "...", "body_en": "...", "title_ru": "...", "body_ru": "...", "hashtags": [...], "image_prompt": "...", "content_type": "market_analysis|prediction"}""",
            "image_prompt_template": "Data visualization concept with Dubai skyline background, modern infographic style, teal and navy colors, professional, 16:9 aspect ratio",
        },
        {
            "name": "Dubai Lifestyle & Trending",
            "category": "lifestyle",
            "tone": "exciting",
            "language": "both",
            "max_length_chars": 1500,
            "prompt_template": """You are the content writer for IDIGOV Real Estate's Telegram channel.

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
{"title_en": "...", "body_en": "...", "title_ru": "...", "body_ru": "...", "hashtags": [...], "image_prompt": "...", "content_type": "lifestyle|events|tourism|food_dining|sports|transportation|culture|entertainment|tech|regulation|construction|health|environment|government|business|general"}""",
            "image_prompt_template": "Vibrant photo of {subject} in Dubai, modern lifestyle, bright colors, engaging composition, no text overlays, photorealistic, 16:9 aspect ratio",
        },
    ]

    for template_data in templates_data:
        # Check if template exists
        result = await db.execute(
            select(PostTemplate).where(PostTemplate.name == template_data["name"])
        )
        if result.scalar_one_or_none():
            print(f"  Template {template_data['name']} already exists, skipping...")
            continue

        template = PostTemplate(**template_data)
        db.add(template)
        print(f"  Created template: {template_data['name']}")

    await db.commit()


async def main():
    """Run all seed functions."""
    print("🌱 Seeding database...")

    async with AsyncSessionLocal() as db:
        print("\n📦 Creating users...")
        await seed_users(db)

        print("\n📰 Creating scrape sources...")
        await seed_scrape_sources(db)

        print("\n📝 Creating post templates...")
        await seed_templates(db)

    print("\n✅ Database seeding complete!")
    print("\nDefault login credentials:")
    print("  Admin: admin@idigov.com / Admin123!")
    print("  SMM:   smm@idigov.com / Smm123!")
    print("  Viewer: viewer@idigov.com / Viewer123!")


if __name__ == "__main__":
    asyncio.run(main())
