"""
Placeholder relevance scoring for scraped articles.
Will be replaced with AI-based scoring in a later phase.
"""
from app.services.scraper.base import ScrapedItem


def calculate_relevance_score(item: ScrapedItem, category: str) -> float:
    """
    Calculate placeholder relevance score (0-1).

    For now, uses simple heuristics. Will be replaced with
    Claude API-based scoring in content generation phase.

    Args:
        item: The scraped item to score
        category: The source category (e.g., "real_estate", "economy")

    Returns:
        Relevance score between 0 and 1
    """
    score = 0.5  # Base score

    # Boost for having full content
    if item.full_text and len(item.full_text) > 200:
        score += 0.1

    # Boost for having image
    if item.image_url:
        score += 0.1

    # Boost for having author
    if item.author:
        score += 0.05

    # Boost for having publish date
    if item.published_at:
        score += 0.05

    # Category-specific keyword boosts
    dubai_keywords = [
        "dubai",
        "uae",
        "emirates",
        "abu dhabi",
        "sharjah",
        "ajman",
        "ras al khaimah",
    ]
    real_estate_keywords = [
        "property",
        "real estate",
        "villa",
        "apartment",
        "rent",
        "sale",
        "developer",
        "emaar",
        "damac",
        "nakheel",
        "meraas",
        "sobha",
        "dewa",
        "ejari",
    ]

    title_lower = item.title.lower()
    text_to_check = title_lower

    if item.summary:
        text_to_check += " " + item.summary.lower()

    # Boost for Dubai relevance
    if any(kw in text_to_check for kw in dubai_keywords):
        score += 0.1

    # Boost for real estate relevance (if applicable category)
    if category == "real_estate" and any(
        kw in text_to_check for kw in real_estate_keywords
    ):
        score += 0.1

    return min(score, 1.0)


def calculate_engagement_potential(item: ScrapedItem) -> float:
    """
    Calculate placeholder engagement potential (0-1).

    Measures how likely the content is to generate engagement.
    Will be enhanced with AI scoring later.

    Args:
        item: The scraped item to score

    Returns:
        Engagement potential score between 0 and 1
    """
    score = 0.5  # Base score

    # Titles with numbers tend to perform well
    if any(char.isdigit() for char in item.title):
        score += 0.1

    # Questions engage readers
    if "?" in item.title:
        score += 0.1

    # Excitement/news indicators
    excitement_words = [
        "new",
        "first",
        "breaking",
        "exclusive",
        "record",
        "largest",
        "biggest",
        "major",
        "announces",
        "launches",
        "revealed",
        "update",
    ]
    title_lower = item.title.lower()
    if any(word in title_lower for word in excitement_words):
        score += 0.1

    # Having an image helps engagement
    if item.image_url:
        score += 0.1

    # Longer content may indicate more substantial article
    if item.full_text and len(item.full_text) > 500:
        score += 0.05

    return min(score, 1.0)
