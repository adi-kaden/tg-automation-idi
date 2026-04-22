"""
Content Generator using Claude API.

Generates bilingual (EN/RU) Telegram posts from scraped articles.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import time

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class GeneratedPost:
    """Result of content generation."""
    title_ru: str
    body_ru: str
    image_prompt: str
    category: str
    quality_score: float
    # Keep EN fields for backwards compatibility (empty strings)
    title_en: str = ""
    body_en: str = ""
    # Hashtags no longer used but kept for compatibility
    hashtags: list[str] = None
    # Claude-selected visual style (one of STYLE_PROMPTS keys)
    image_style: str = ""
    # Album mode: list of distinct image prompts for a media group
    album_image_prompts: list[str] | None = None

    def __post_init__(self):
        if self.hashtags is None:
            self.hashtags = []
        if self.album_image_prompts is None:
            self.album_image_prompts = []


SYSTEM_PROMPT = """You are an expert social media content creator for IDIGOV Real Estate, a premium real estate company in Dubai, UAE. You create engaging Telegram posts in Russian for the Russian-speaking audience of Dubai property investors.

FORMATTING RULES (CRITICAL — Telegram does NOT render Markdown):
- Output body_ru as Telegram-compatible HTML ONLY. Never use Markdown.
- NEVER write **bold**, __bold__, *italic*, _italic_, ~~strike~~, `code`, or > quote.
  Telegram will render those as literal characters, not formatting.
- WRONG:  "цена выросла на **15%**"   →  user sees literal asterisks
- RIGHT:  "цена выросла на <b>15%</b>" →  user sees bold

ALLOWED HTML TAGS (use them liberally for visual rhythm):
- <b>text</b>            — bold. Use for numbers, prices, percentages, key terms.
- <i>text</i>            — italic. Use for emphasis, foreign terms, soft callouts.
- <u>text</u>            — underline. Use sparingly for one standout phrase.
- <s>text</s>            — strikethrough. Use for before/after price comparisons (e.g. <s>800K</s> → <b>650K AED</b>).
- <code>text</code>      — monospaced. Use for specific terms, codes, addresses.
- <blockquote>text</blockquote>           — quote block. Use for data/stats callouts, dramatic takeaways, expert quotes.
- <blockquote expandable>text</blockquote> — expandable quote. Use for longer callouts (>100 chars) so the feed stays clean.
- <tg-spoiler>text</tg-spoiler>           — hidden until tapped. Use for teaser numbers (e.g. "доходность до <tg-spoiler>12%</tg-spoiler>").
- <a href="https://...">text</a>          — hyperlinks. Only use https:// URLs.

FORBIDDEN TAGS (will break the message):
- <p>, <div>, <br>, <span>, <h1>-<h6>, <strong>, <em>, <ul>, <li>
- Use \\n for line breaks (NOT <br>). Use blank lines between paragraphs.

EDITORIAL RULES:
- Title must start with a relevant emoji. No HTML tags inside the title.
- Bold the most impactful numbers, statistics, prices. Not every number — pick the 2-3 that matter.
- Use <blockquote> for at least one quote/callout per post where editorially appropriate.
- Mix formatting tools: a post with only <b> looks flat. Try <b> + <i> + <blockquote> together.
- Every sentence must deliver value — no filler, no generic statements, no "water".

CHARACTER LIMIT:
The ENTIRE Telegram message (title + body HTML + channel footer) must fit within 1024 characters INCLUDING all HTML tags. Aim for body text of ~500-600 characters to leave room for title, tags, and footer.

IMPORTANT: All content must be written in Russian. Target audience: Russian-speaking investors and business people interested in Dubai real estate."""


# Voice preset system prompt blocks appended to the base system prompt.
VOICE_PRESETS = {
    "professional": """VOICE PRESET — PROFESSIONAL:
- Measured, authoritative tone with industry terminology
- Structured paragraphs, formal transitions
- Bold only the most critical numbers/terms
- Blockquotes for official statements or data sources
- 1-2 emojis per post""",

    "punchy": """VOICE PRESET — PUNCHY:
- Short punchy sentences. Mash/tabloid style.
- Every sentence must hit hard — no filler
- Aggressively bold key stats, numbers, money figures
- Blockquotes for dramatic effect or key takeaways
- 2-3 emojis, one always in the title""",

    "analytical": """VOICE PRESET — ANALYTICAL:
- Data-first approach: numbers lead each section
- Comparative analysis (before/after, vs competitor, YoY)
- Bold all numerical data and percentages
- Blockquotes for methodology notes or data sources
- 1 emoji max, only in title""",
}


def build_system_prompt(voice_preset: str = "professional", base_system_prompt: str | None = None) -> str:
    """Combine the base system prompt with the chosen voice preset block."""
    base = base_system_prompt or SYSTEM_PROMPT
    voice_block = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["professional"])
    return f"{base}\n\n{voice_block}"


def _markdown_to_html(text: str) -> str:
    """
    Convert common Markdown patterns to Telegram HTML.

    The system prompt forbids Markdown, but Claude sometimes slips into it
    anyway. This is a safety net so the post renders correctly regardless.
    Only conversions that are unambiguous and safe are performed here.
    """
    # ~~strike~~  →  <s>strike</s>   (run first so the ~~ isn't eaten by anything else)
    text = re.sub(r"~~(?!\s)(.+?)(?<!\s)~~", r"<s>\1</s>", text, flags=re.DOTALL)

    # **bold**  →  <b>bold</b>   (most common issue — do before single-* to avoid collision)
    text = re.sub(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)

    # __bold__  →  <b>bold</b>   (alternative Markdown bold)
    text = re.sub(r"__(?!\s)(.+?)(?<!\s)__", r"<b>\1</b>", text, flags=re.DOTALL)

    # `code`  →  <code>code</code>   (inline code; single backticks, no newlines)
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)

    # Single *italic* and _italic_ are deliberately NOT converted — they're
    # ambiguous with bullet points, word-internal underscores, and emphasis
    # in prose. Better to leave them than to mangle text.

    # Leading "> " on a line → wrap the whole line in <blockquote>…</blockquote>
    # Handle contiguous quote lines as a single block.
    def _blockquote_replace(match: re.Match) -> str:
        block = match.group(0)
        # Strip the leading "> " from each line
        lines = [re.sub(r"^>\s?", "", ln) for ln in block.splitlines()]
        return "<blockquote>" + "\n".join(lines) + "</blockquote>"

    text = re.sub(
        r"(?m)^>[^\n]*(?:\n^>[^\n]*)*",
        _blockquote_replace,
        text,
    )

    return text


def _repair_html(text: str) -> str:
    """
    Normalize AI output for Telegram:
      1. Convert any Markdown the model slipped into to HTML.
      2. Close any unclosed <b>, <i>, <u>, <s>, <code>, or <blockquote> tags.
    """
    text = _markdown_to_html(text)

    # Tags to track in order: opening increases depth, closing decreases.
    # Order matters — close inner tags before outer ones would, so list
    # block tags last.
    tag_patterns = [
        ("b", re.compile(r"<b>", re.IGNORECASE), re.compile(r"</b>", re.IGNORECASE)),
        ("i", re.compile(r"<i>", re.IGNORECASE), re.compile(r"</i>", re.IGNORECASE)),
        ("u", re.compile(r"<u>", re.IGNORECASE), re.compile(r"</u>", re.IGNORECASE)),
        ("s", re.compile(r"<s>", re.IGNORECASE), re.compile(r"</s>", re.IGNORECASE)),
        ("code", re.compile(r"<code>", re.IGNORECASE), re.compile(r"</code>", re.IGNORECASE)),
        ("tg-spoiler", re.compile(r"<tg-spoiler>", re.IGNORECASE), re.compile(r"</tg-spoiler>", re.IGNORECASE)),
        ("blockquote", re.compile(r"<blockquote(?:\s+expandable)?>", re.IGNORECASE), re.compile(r"</blockquote>", re.IGNORECASE)),
    ]
    result = text
    for tag_name, open_re, close_re in tag_patterns:
        opens = len(open_re.findall(result))
        closes = len(close_re.findall(result))
        unclosed = opens - closes
        if unclosed > 0:
            result = result + f"</{tag_name}>" * unclosed
    return result


def _build_recent_posts_section(recent_posts: list[dict]) -> str:
    """Build a prompt section listing already-covered topics to avoid repetition."""
    if not recent_posts:
        return ""
    lines = []
    for i, p in enumerate(recent_posts, 1):
        lines.append(f"{i}. {p['title']} — {p['body_snippet']}...")
    posts_text = "\n".join(lines)
    return f"""

ALREADY COVERED TOPICS (DO NOT repeat these — choose a COMPLETELY DIFFERENT subject):
{posts_text}

CRITICAL: You MUST write about a topic that is NOT covered above.
Do not rewrite, rephrase, or cover the same events/news even from a different angle.
If all source articles are about topics already covered, find a secondary detail or a completely different story from the articles."""


def _build_generation_prompt(
    articles: list[dict],
    content_type: str,
    category: str,
    template: Optional[dict] = None,
    prompt_config: Optional[dict] = None,
    recent_posts: Optional[list[dict]] = None,
    album_mode: bool = False,
) -> str:
    """Build the prompt for content generation.

    If prompt_config is provided with a generation_prompt template,
    it replaces the hardcoded prompt with variable substitution.
    """

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

    content_type_enforcement = ""
    if content_type == "real_estate":
        content_type_enforcement = """
STRICT REQUIREMENT: This post MUST be about Dubai/UAE real estate, property, or construction.
If the source articles are not about real estate, extract any real estate angle (property prices, development impact, investment implications) or use the articles as background context for a real estate-focused post.
Do NOT write a general news post for this slot — it must be relevant to property investors."""

    recent_posts_section = _build_recent_posts_section(recent_posts or [])

    album_section = ""
    if album_mode:
        album_section = """
ALBUM MODE: Generate 2-5 distinct image prompts for a media group album. Each prompt should depict a different visual aspect of the story. Include them in the JSON as "album_image_prompts": ["prompt1", "prompt2", ...]."""

    # If we have a prompt_config with generation_prompt template, use it
    if prompt_config and prompt_config.get("generation_prompt"):
        tone = prompt_config.get("tone", "professional")
        max_length = min(prompt_config.get("max_length_chars", 600), 700)
        generation_template = prompt_config["generation_prompt"]

        # Replace template variables
        result = (
            generation_template
            .replace("{{articles}}", articles_text)
            .replace("{{content_type}}", content_type)
            .replace("{{category}}", f"{category} ({topic_focus})")
            .replace("{{tone}}", tone)
            .replace("{{max_length}}", str(max_length))
            .replace("{{guidance}}", guidance)
            .replace("{{recent_posts}}", recent_posts_section)
        )
        # If template didn't have {{recent_posts}} placeholder, append the section
        if recent_posts_section and "RECENTLY PUBLISHED" not in result:
            result += recent_posts_section
        if content_type_enforcement:
            result += content_type_enforcement
        if album_section:
            result += album_section
        return result

    # Legacy: support old template dict
    template_section = ""
    if template:
        template_section = f"""
Use this template as a style guide:
Tone: {template.get('tone', 'professional')}
Max Length: {template.get('max_length_chars', 600)} characters
Example style: {template.get('example_output', 'N/A')}
"""

    album_json_field = ""
    if album_mode:
        album_json_field = '\n    "album_image_prompts": ["...", "...", ...],'

    return f"""Based on the following news articles, create a compelling Telegram post in Russian for IDIGOV Real Estate's channel.

Content Type: {content_type}
Focus Area: {guidance}
Category: {category} ({topic_focus})
{content_type_enforcement}
{template_section}

SOURCE ARTICLES:
{articles_text}
{recent_posts_section}
Generate a Telegram post with the following structure (ALL IN RUSSIAN):

1. TITLE (Russian): A catchy, engaging headline in Russian starting with a relevant emoji (max 100 chars)
2. BODY (Russian): The main post content as Telegram HTML. NEVER use Markdown (**, __, *, _, ~~, `, >).
   ALLOWED TAGS: <b>, <i>, <u>, <s>, <code>, <blockquote>, <blockquote expandable>, <tg-spoiler>, <a href="https://...">
   FORBIDDEN TAGS: <p>, <div>, <br>, <span>, <strong>, <em>, <h1>-<h6>, <ul>, <li>
   Use \\n for line breaks (NOT <br>). Blank lines between paragraphs.
   CRITICAL: The ENTIRE Telegram message (title + body + footer) must fit within 1024 characters INCLUDING HTML tags.
   Aim for ~500-600 characters of body text.
   FORMATTING TIPS: Bold key numbers/prices with <b>. Use <i> for emphasis. Use <s> for crossed-out old prices
   (e.g. <s>800K</s> → <b>650K AED</b>). Use <blockquote> for dramatic callouts or expert quotes.
   Use <tg-spoiler> for teaser numbers. Mix at least 2 different formatting tags per post for visual rhythm.
   Do NOT include hashtags.
3. IMAGE_PROMPT: A detailed prompt for generating an accompanying image (describe the visual concept, composition, subject matter - suitable for a real estate/Dubai context). Do NOT include style/lighting/color instructions — a separate style layer will be applied.
4. QUALITY_SCORE: Rate the newsworthiness and engagement potential (0.0-1.0)
5. IMAGE_STYLE: Choose the single most appropriate visual style for the image based on the post content:
   - "conceptual_photography" — Cinematic, dramatic lighting, premium textures, luxury mood
   - "architectural_visualization" — Futuristic architecture, dramatic perspective, hyper-realistic
   - "editorial_still_life" — Soft natural light, carefully arranged objects, minimalist
   - "abstract_artistic" — Extreme close-up, textures, patterns, fine art macro photography
   - "aerial_cinematic" — Drone/overhead perspective, sweeping urban views, golden hour
   - "surreal_dreamlike" — Magical/impossible elements, ethereal soft lighting, fantasy blend
{album_section}
Respond in JSON format:
{{
    "title_ru": "...",
    "body_ru": "...",
    "image_prompt": "...",
    "quality_score": 0.85,
    "image_style": "conceptual_photography"{album_json_field}
}}"""


class ContentGenerator:
    """
    Generate Telegram post content using Claude API.
    """

    def __init__(self):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-6"

    async def generate_post(
        self,
        articles: list[dict],
        content_type: str,
        category: str,
        template: Optional[dict] = None,
        prompt_config: Optional[dict] = None,
        recent_posts: Optional[list[dict]] = None,
        voice_preset: str = "professional",
        album_mode: bool = False,
    ) -> GeneratedPost:
        """
        Generate a bilingual Telegram post from source articles.

        Args:
            articles: List of scraped article dicts (title, summary, url)
            content_type: "real_estate" or "general_dubai"
            category: Specific category (real_estate_news, lifestyle, etc.)
            template: Optional template dict for style guidance (legacy)
            prompt_config: Optional dict with system_prompt, generation_prompt, tone, etc.
            recent_posts: Optional list of recently published posts to avoid topic repetition
            voice_preset: Voice style preset ("professional", "punchy", "analytical")
            album_mode: If True, request album_image_prompts from Claude

        Returns:
            GeneratedPost with bilingual content
        """
        if not articles:
            raise ValueError("At least one article required for generation")

        prompt = _build_generation_prompt(
            articles, content_type, category, template, prompt_config, recent_posts, album_mode
        )

        # Determine which voice preset to use: prompt_config may carry one
        effective_preset = voice_preset
        if prompt_config and prompt_config.get("voice_preset"):
            effective_preset = prompt_config["voice_preset"]

        # Use system prompt from config if available, otherwise default
        base_system_prompt = None
        if prompt_config and prompt_config.get("system_prompt"):
            base_system_prompt = prompt_config["system_prompt"]

        system_prompt = build_system_prompt(effective_preset, base_system_prompt)

        logger.info(
            f"Generating post for {content_type}/{category} from {len(articles)} articles "
            f"[voice={effective_preset}, album={album_mode}]"
        )

        max_rate_limit_retries = 3
        rate_limit_attempt = 0

        while True:
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    system=system_prompt,
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

                # Repair any unclosed HTML tags in body_ru
                body_ru = _repair_html(data.get("body_ru", ""))

                return GeneratedPost(
                    title_en=data.get("title_en", ""),
                    body_en=data.get("body_en", ""),
                    title_ru=data.get("title_ru", ""),
                    body_ru=body_ru,
                    hashtags=data.get("hashtags", []),
                    image_prompt=data.get("image_prompt", ""),
                    category=category,
                    quality_score=float(data.get("quality_score", 0.5)),
                    image_style=data.get("image_style", ""),
                    album_image_prompts=data.get("album_image_prompts") or [],
                )

            except anthropic.RateLimitError as e:
                rate_limit_attempt += 1
                if rate_limit_attempt > max_rate_limit_retries:
                    logger.error(f"Claude API rate limit exceeded after {max_rate_limit_retries} retries")
                    raise

                # Parse Retry-After header if available, default to 60s
                retry_after = 60
                if hasattr(e, 'response') and e.response is not None:
                    header_val = e.response.headers.get("retry-after")
                    if header_val:
                        try:
                            retry_after = max(int(header_val), 30)
                        except (ValueError, TypeError):
                            pass

                logger.warning(
                    f"Claude API rate limited (attempt {rate_limit_attempt}/{max_rate_limit_retries}), "
                    f"waiting {retry_after}s before retry"
                )
                time.sleep(retry_after)

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
Title (RU): {original_post.title_ru}
Body (RU): {original_post.body_ru}

Please revise the "{section}" section based on this feedback:
{instructions}

Return the COMPLETE post in the same JSON format, with only the requested section modified.
body_ru must use Telegram-compatible HTML (<b>, <i>, <blockquote> only; \\n for line breaks):
{{
    "title_ru": "...",
    "body_ru": "...",
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

            body_ru = _repair_html(data.get("body_ru", original_post.body_ru))

            return GeneratedPost(
                title_en=data.get("title_en", original_post.title_en),
                body_en=data.get("body_en", original_post.body_en),
                title_ru=data.get("title_ru", original_post.title_ru),
                body_ru=body_ru,
                hashtags=data.get("hashtags", original_post.hashtags),
                image_prompt=data.get("image_prompt", original_post.image_prompt),
                category=original_post.category,
                quality_score=float(data.get("quality_score", original_post.quality_score)),
                image_style=data.get("image_style", original_post.image_style),
                album_image_prompts=data.get("album_image_prompts") or original_post.album_image_prompts,
            )

        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.error(f"Failed to regenerate section: {e}")
            raise
