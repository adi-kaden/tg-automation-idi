"""
Content Generator using Claude API.

Generates bilingual (EN/RU) Telegram posts from scraped articles.
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class GeneratedPost:
    """Result of content generation."""
    title_en: str
    body_en: str
    title_ru: str
    body_ru: str
    hashtags: list[str]
    image_prompt: str
    category: str
    quality_score: float


SYSTEM_PROMPT = """You are an expert social media content creator for IDIGOV Real Estate, a premium real estate company in Dubai, UAE. You create engaging Telegram posts about Dubai real estate, market trends, and lifestyle news.

Your posts should:
1. Be informative yet engaging
2. Appeal to property investors, expatriates, and Dubai enthusiasts
3. Use a professional but approachable tone
4. Include relevant emojis sparingly (1-3 per post)
5. Be concise - ideal for Telegram reading

IMPORTANT: Generate content in BOTH English and Russian. The Russian audience is a significant segment of Dubai property investors."""


def _build_generation_prompt(
    articles: list[dict],
    content_type: str,
    category: str,
    template: Optional[dict] = None,
) -> str:
    """Build the prompt for content generation."""

    # Format article information
    articles_text = "\n\n".join([
        f"Article {i+1}:\nTitle: {a.get('title', 'N/A')}\nSummary: {a.get('summary', 'N/A')}\nURL: {a.get('url', 'N/A')}"
        for i, a in enumerate(articles[:5])  # Limit to 5 articles
    ])

    content_type_guidance = {
        "real_estate": "Focus on property market insights, investment opportunities, new developments, and real estate regulations in Dubai/UAE.",
        "general_dubai": "Cover Dubai lifestyle, economy, business news, technology, tourism, events, and general interest stories.",
    }

    category_topics = {
        "real_estate_news": "property transactions, new listings, market movements",
        "market_analysis": "market trends, price analysis, investment ROI",
        "prediction": "market forecasts, upcoming developments, price predictions",
        "economy": "economic indicators, business climate, trade news",
        "tech": "proptech, smart homes, technology innovations",
        "construction": "new projects, infrastructure, building developments",
        "regulation": "property laws, visa updates, government policies",
        "lifestyle": "Dubai living, luxury amenities, expat life",
        "events": "exhibitions, conferences, community events",
        "tourism": "tourist attractions, hospitality, visitor trends",
        "general": "general news and updates about Dubai",
    }

    guidance = content_type_guidance.get(content_type, content_type_guidance["general_dubai"])
    topic_focus = category_topics.get(category, category_topics["general"])

    template_section = ""
    if template:
        template_section = f"""
Use this template as a style guide:
Tone: {template.get('tone', 'professional')}
Max Length: {template.get('max_length_chars', 1500)} characters
Example style: {template.get('example_output', 'N/A')}
"""

    return f"""Based on the following news articles, create a compelling Telegram post for IDIGOV Real Estate's channel.

Content Type: {content_type}
Focus Area: {guidance}
Category: {category} ({topic_focus})
{template_section}

SOURCE ARTICLES:
{articles_text}

Generate a Telegram post with the following structure:

1. TITLE (English): A catchy, engaging headline (max 100 chars)
2. BODY (English): The main post content (400-800 chars). Include key facts, insights, and a subtle call-to-action if relevant.
3. TITLE (Russian): Translation of the English title, adapted for Russian-speaking audience
4. BODY (Russian): Translation of the English body, adapted for Russian-speaking audience
5. HASHTAGS: 3-5 relevant hashtags (in English)
6. IMAGE_PROMPT: A detailed prompt for generating an accompanying image (describe the visual concept, style, colors - suitable for a real estate/Dubai context)
7. QUALITY_SCORE: Rate the newsworthiness and engagement potential (0.0-1.0)

Respond in JSON format:
{{
    "title_en": "...",
    "body_en": "...",
    "title_ru": "...",
    "body_ru": "...",
    "hashtags": ["#Dubai", "#RealEstate", ...],
    "image_prompt": "...",
    "quality_score": 0.85
}}"""


class ContentGenerator:
    """
    Generate Telegram post content using Claude API.
    """

    def __init__(self):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    async def generate_post(
        self,
        articles: list[dict],
        content_type: str,
        category: str,
        template: Optional[dict] = None,
    ) -> GeneratedPost:
        """
        Generate a bilingual Telegram post from source articles.

        Args:
            articles: List of scraped article dicts (title, summary, url)
            content_type: "real_estate" or "general_dubai"
            category: Specific category (real_estate_news, lifestyle, etc.)
            template: Optional template dict for style guidance

        Returns:
            GeneratedPost with bilingual content
        """
        if not articles:
            raise ValueError("At least one article required for generation")

        prompt = _build_generation_prompt(articles, content_type, category, template)

        logger.info(f"Generating post for {content_type}/{category} from {len(articles)} articles")

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            # Extract the response content
            response_text = message.content[0].text

            # Parse JSON response
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())

            return GeneratedPost(
                title_en=data.get("title_en", ""),
                body_en=data.get("body_en", ""),
                title_ru=data.get("title_ru", ""),
                body_ru=data.get("body_ru", ""),
                hashtags=data.get("hashtags", []),
                image_prompt=data.get("image_prompt", ""),
                category=category,
                quality_score=float(data.get("quality_score", 0.5)),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Response was: {response_text[:500]}")
            raise ValueError(f"Invalid JSON response from Claude: {e}")
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def regenerate_section(
        self,
        original_post: GeneratedPost,
        section: str,
        instructions: str,
    ) -> GeneratedPost:
        """
        Regenerate a specific section of a post based on feedback.

        Args:
            original_post: The original generated post
            section: Which section to regenerate (title_en, body_ru, etc.)
            instructions: Human feedback on what to change

        Returns:
            Updated GeneratedPost
        """
        prompt = f"""Here is an existing Telegram post that needs revision:

CURRENT POST:
Title (EN): {original_post.title_en}
Body (EN): {original_post.body_en}
Title (RU): {original_post.title_ru}
Body (RU): {original_post.body_ru}
Hashtags: {', '.join(original_post.hashtags)}

Please revise the "{section}" section based on this feedback:
{instructions}

Return the COMPLETE post in the same JSON format, with only the requested section modified:
{{
    "title_en": "...",
    "body_en": "...",
    "title_ru": "...",
    "body_ru": "...",
    "hashtags": [...],
    "image_prompt": "...",
    "quality_score": ...
}}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            response_text = message.content[0].text

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())

            return GeneratedPost(
                title_en=data.get("title_en", original_post.title_en),
                body_en=data.get("body_en", original_post.body_en),
                title_ru=data.get("title_ru", original_post.title_ru),
                body_ru=data.get("body_ru", original_post.body_ru),
                hashtags=data.get("hashtags", original_post.hashtags),
                image_prompt=data.get("image_prompt", original_post.image_prompt),
                category=original_post.category,
                quality_score=float(data.get("quality_score", original_post.quality_score)),
            )

        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.error(f"Failed to regenerate section: {e}")
            raise
