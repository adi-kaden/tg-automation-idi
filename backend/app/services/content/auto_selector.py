"""
Auto Selector using Claude API.

Automatically selects the best post option when SMM doesn't choose before deadline.
"""
import json
import logging
from typing import Optional

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


SELECTOR_SYSTEM_PROMPT = """You are an expert social media content analyst for IDIGOV Real Estate in Dubai. Your job is to select the best Telegram post option for publication.

Evaluate posts based on:
1. Engagement potential - will this capture attention and drive interaction?
2. News value - how timely and important is the information?
3. Brand alignment - does it reflect IDIGOV's professional, premium image?
4. Content quality - is it well-written, informative, and clear?
5. Visual appeal - is the accompanying image concept compelling?

For real estate content, prioritize market insights and investment opportunities.
For general Dubai content, prioritize trending topics and lifestyle appeal."""


class AutoSelector:
    """
    Automatically select the best post option using Claude API.
    """

    def __init__(self):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-6"

    async def select_best_option(
        self,
        options: list[dict],
        content_type: str,
        slot_time: str,
    ) -> tuple[str, str, float]:
        """
        Select the best post option from available choices.

        Args:
            options: List of post option dicts with keys:
                - option_label (A/B)
                - title_en, body_en, title_ru, body_ru
                - hashtags, image_prompt
                - ai_quality_score
            content_type: "real_estate" or "general_dubai"
            slot_time: The scheduled posting time (for context)

        Returns:
            Tuple of (selected_option_label, reasoning, confidence_score)
        """
        if not options:
            raise ValueError("No options provided for selection")

        if len(options) == 1:
            return (options[0]["option_label"], "Only one option available", 1.0)

        # Format options for comparison (Russian only)
        options_text = ""
        for opt in options:
            options_text += f"""
=== OPTION {opt['option_label']} ===
Заголовок: {opt['title_ru']}
Текст: {opt['body_ru'][:500]}...

Hashtags: {opt.get('hashtags', [])}
Image Concept: {opt.get('image_prompt', 'N/A')[:200]}
AI Quality Score: {opt.get('ai_quality_score', 'N/A')}

"""

        prompt = f"""Compare these Russian Telegram post options and select the best one for publication.

Content Type: {content_type}
Scheduled Time: {slot_time}

{options_text}

Analyze each option and select the best one for our Russian-speaking audience of property investors and Dubai enthusiasts.

Respond in JSON format:
{{
    "selected_option": "A" or "B",
    "reasoning": "Brief explanation of why this option is better (2-3 sentences)",
    "confidence": 0.0-1.0 (how confident you are in this selection)
}}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=SELECTOR_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            response_text = message.content[0].text

            # Parse JSON response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())

            selected = data.get("selected_option", "A")
            reasoning = data.get("reasoning", "Selected based on overall quality")
            confidence = float(data.get("confidence", 0.7))

            logger.info(f"Auto-selected option {selected} with confidence {confidence}")

            return (selected, reasoning, confidence)

        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.error(f"Auto-selection failed: {e}")
            # Fallback to option with highest quality score
            best = max(options, key=lambda x: x.get("ai_quality_score", 0))
            return (best["option_label"], "Fallback selection based on quality score", 0.5)

    async def evaluate_post_quality(
        self,
        post: dict,
        content_type: str,
    ) -> dict:
        """
        Evaluate a single post's quality for feedback.

        Args:
            post: Post dict with title_en, body_en, etc.
            content_type: Content type for context

        Returns:
            Dict with scores and improvement suggestions
        """
        prompt = f"""Evaluate this Telegram post for quality:

Title (EN): {post.get('title_en', '')}
Body (EN): {post.get('body_en', '')}
Title (RU): {post.get('title_ru', '')}
Body (RU): {post.get('body_ru', '')}
Content Type: {content_type}

Rate each aspect 1-10 and provide brief improvement suggestions:

Respond in JSON:
{{
    "engagement_score": 1-10,
    "clarity_score": 1-10,
    "brand_alignment_score": 1-10,
    "translation_quality_score": 1-10,
    "overall_score": 1-10,
    "strengths": ["...", "..."],
    "improvements": ["...", "..."]
}}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=SELECTOR_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            response_text = message.content[0].text

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text.strip())

        except Exception as e:
            logger.error(f"Post evaluation failed: {e}")
            return {
                "overall_score": 5,
                "error": str(e),
            }
