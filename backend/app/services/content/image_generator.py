"""
Image Generator using Google Imagen API.

Generates images for Telegram posts based on prompts.
"""
import asyncio
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Predefined visual styles for Claude-driven selection ─────────
STYLE_PROMPTS = {
    "conceptual_photography": (
        "Style: Cinematic conceptual photography with dramatic lighting and premium textures. "
        "Deep shadows, rich contrast, and carefully composed scenes that evoke luxury and sophistication. "
        "Think high-end advertising campaign with a focus on mood and atmosphere. "
        "Quality: Ultra high resolution, shallow depth of field, professional studio or location lighting. "
        "Colors: Rich warm tones with deep blacks and golden highlights. "
        "Note: No text, watermarks, or people's faces in the image."
    ),
    "architectural_visualization": (
        "Style: Futuristic architectural concept art with dramatic perspective and scale. "
        "Towering modern structures, sweeping lines, glass and steel facades reflecting city lights and sky. "
        "Hyper-realistic rendering with cinematic composition. "
        "Quality: Photorealistic 3D visualization quality, dramatic wide-angle perspective. "
        "Colors: Cool blues and silvers with warm accent lighting, sunset or golden hour sky. "
        "Note: No text, watermarks, or people's faces in the image."
    ),
    "editorial_still_life": (
        "Style: High-end editorial still life photography with soft natural light. "
        "Carefully arranged objects, documents, or architectural models on premium surfaces. "
        "Minimalist composition with intentional negative space. "
        "Quality: Magazine editorial quality, soft diffused lighting, precise focus. "
        "Colors: Neutral palette with subtle warm accents, cream and sand tones. "
        "Note: No text, watermarks, or people's faces in the image."
    ),
    "abstract_artistic": (
        "Style: Abstract premium art photography with extreme close-up textures and patterns. "
        "Fine art approach to real estate and urban themes — marble veins, glass reflections, water patterns, "
        "geometric architectural details. Macro photography meets modern art. "
        "Quality: Gallery-quality fine art photography, precise detail, artistic blur. "
        "Colors: Monochromatic or limited palette with one striking accent color. "
        "Note: No text, watermarks, or people's faces in the image."
    ),
    "aerial_cinematic": (
        "Style: Cinematic aerial photography from drone or overhead perspective. "
        "Sweeping views of urban landscapes, coastlines, developments, and infrastructure. "
        "Golden hour or blue hour lighting with long dramatic shadows. "
        "Quality: Ultra-wide cinematic aspect, sharp detail across the frame, atmospheric haze. "
        "Colors: Warm golden tones at golden hour, or deep blues and city lights at twilight. "
        "Note: No text, watermarks, or people's faces in the image."
    ),
    "surreal_dreamlike": (
        "Style: Surrealist photography with dreamlike atmosphere and impossible elements. "
        "Blend reality with fantasy — floating structures, mirror-like water, impossible architecture, "
        "ethereal soft lighting, and magical atmospheric effects. "
        "Quality: High-end digital art quality, soft ethereal glow, perfect compositing. "
        "Colors: Pastel and iridescent tones with soft gradients and luminous highlights. "
        "Note: No text, watermarks, or people's faces in the image."
    ),
}

DEFAULT_IMAGE_STYLE = "conceptual_photography"


def build_final_image_prompt(claude_image_prompt: str, image_style: str) -> str:
    """Combine Claude's content-specific prompt with a predefined visual style."""
    style_suffix = STYLE_PROMPTS.get(image_style, STYLE_PROMPTS[DEFAULT_IMAGE_STYLE])
    return f"{claude_image_prompt}\n\n{style_suffix}"


class ImageGenerator:
    """
    Generate images using Google Imagen 4.0 API.
    """

    def __init__(self, output_dir: str = "generated_images"):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "imagen-4.0-generate-001"

        # Setup output directory
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _enhance_prompt(
        self,
        base_prompt: str,
        category: str,
        prompt_config: dict | None = None,
        image_style: str | None = None,
    ) -> str:
        """Enhance the image prompt with style guidance.

        Priority:
        1. Claude-selected style from STYLE_PROMPTS (new default path)
        2. Manual override from prompt_config.image_style_prompt (legacy escape hatch)
        3. Legacy category-based fallback
        """
        # Priority 1: Claude-selected style
        if image_style and image_style in STYLE_PROMPTS:
            return build_final_image_prompt(base_prompt, image_style)

        # Priority 2: Manual override from prompt_config
        if prompt_config and prompt_config.get("image_style_prompt"):
            return f"{base_prompt}\n\n{prompt_config['image_style_prompt']}"

        # Priority 3: Legacy category-based fallback
        style_guidance = {
            "real_estate_news": "Modern luxury Dubai architecture, professional real estate photography style, golden hour lighting, high-end finishes",
            "market_analysis": "Clean professional infographic style, data visualization, modern minimal design, Dubai skyline silhouette",
            "prediction": "Futuristic Dubai cityscape, modern architecture, forward-looking perspective, sleek design",
            "economy": "Business district, corporate skyline, professional financial imagery, Dubai financial center",
            "tech": "Smart city visualization, modern technology, innovative design, futuristic Dubai",
            "construction": "Construction progress, modern architecture emerging, cranes and development, Dubai growth",
            "regulation": "Official professional style, government buildings, legal and formal imagery",
            "lifestyle": "Luxury Dubai lifestyle, premium amenities, expatriate living, high-end leisure",
            "events": "Dubai events and exhibitions, gathering spaces, professional venues",
            "tourism": "Dubai landmarks, tourist attractions, beautiful cityscapes, iconic views",
            "general": "Modern Dubai, contemporary cityscape, professional photography style",
        }

        style = style_guidance.get(category, style_guidance["general"])

        return f"""{base_prompt}

Style: {style}
Quality: High resolution, professional photography or illustration style
Mood: Professional, aspirational, modern
Colors: Warm tones, gold accents, blues reflecting Dubai's sky and sea
Note: No text or watermarks in the image"""

    async def generate_image(
        self,
        prompt: str,
        category: str,
        slot_id: str,
        option_label: str,
        prompt_config: dict | None = None,
        image_style: str | None = None,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Generate an image for a post option using Imagen 4.0.

        Args:
            prompt: Base image prompt from content generator
            category: Content category for style guidance
            slot_id: Content slot ID for file naming
            option_label: Option label (A/B) for file naming
            prompt_config: Optional config with image_style_prompt, image_aspect_ratio
            image_style: Claude-selected style key from STYLE_PROMPTS

        Returns:
            Tuple of (image_url, local_path, image_base64)
        """
        enhanced_prompt = self._enhance_prompt(prompt, category, prompt_config, image_style)
        aspect_ratio = (prompt_config or {}).get("image_aspect_ratio", "16:9")

        logger.info(f"Generating image for slot {slot_id} option {option_label}")

        try:
            # Generate image using Imagen 4.0
            response = self.client.models.generate_images(
                model=self.model,
                prompt=enhanced_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    safety_filter_level="BLOCK_LOW_AND_ABOVE",
                ),
            )

            if response.generated_images and len(response.generated_images) > 0:
                img = response.generated_images[0]

                # Get image bytes
                image_bytes = img.image.image_bytes

                # Encode as base64 for database storage
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')

                # Also save locally (optional, for debugging)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{slot_id}_{option_label}_{timestamp}.png"
                filepath = self.output_dir / filename
                filepath.write_bytes(image_bytes)

                logger.info(f"Image generated ({len(image_bytes)} bytes), base64 length: {len(image_base64)}")
                return (None, str(filepath), image_base64)

            logger.warning("Imagen did not return any images")
            return (None, None, None)

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            # Don't raise - image is optional, post can go without
            return (None, None, None)

    async def generate_album_images(
        self,
        prompts: list[str],
        category: str,
        slot_id: str,
        option_label: str,
        prompt_config: dict | None = None,
        image_style: str | None = None,
    ) -> list[tuple[Optional[str], Optional[str], Optional[str]]]:
        """
        Generate multiple images for an album/media group.

        Uses asyncio.gather with a semaphore (max 3 concurrent) to balance
        speed vs. API rate limits. Partial failures are tolerated.

        Returns:
            List of (image_url, local_path, image_base64) tuples
        """
        semaphore = asyncio.Semaphore(3)

        async def _generate_one(idx: int, prompt: str):
            async with semaphore:
                return await self.generate_image(
                    prompt=prompt,
                    category=category,
                    slot_id=f"{slot_id}_album{idx}",
                    option_label=option_label,
                    prompt_config=prompt_config,
                    image_style=image_style,
                )

        tasks = [_generate_one(i, p) for i, p in enumerate(prompts)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions, keep successful results
        album_images = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Album image {i} generation failed: {result}")
                album_images.append((None, None, None))
            else:
                album_images.append(result)

        return album_images

    async def generate_image_from_url(
        self,
        image_url: str,
        slot_id: str,
        option_label: str,
    ) -> Optional[str]:
        """
        Download and save an image from URL.

        Args:
            image_url: URL of the image to download
            slot_id: Content slot ID for file naming
            option_label: Option label (A/B) for file naming

        Returns:
            Local file path or None if download failed
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, timeout=30.0)
                response.raise_for_status()

                # Determine file extension from content type
                content_type = response.headers.get("content-type", "image/jpeg")
                ext = "jpg"
                if "png" in content_type:
                    ext = "png"
                elif "webp" in content_type:
                    ext = "webp"

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{slot_id}_{option_label}_{timestamp}.{ext}"
                filepath = self.output_dir / filename

                filepath.write_bytes(response.content)
                logger.info(f"Image downloaded to {filepath}")

                return str(filepath)

        except Exception as e:
            logger.error(f"Failed to download image from {image_url}: {e}")
            return None

    async def create_placeholder_image(
        self,
        slot_id: str,
        option_label: str,
        category: str,
    ) -> Optional[str]:
        """
        Create a simple placeholder image when generation fails.

        This is a fallback - in production, you might use a set of
        pre-designed template images based on category.

        Args:
            slot_id: Content slot ID
            option_label: Option label
            category: Content category

        Returns:
            Path to placeholder image or None
        """
        # For now, just return None - placeholder implementation
        # In production, could return a pre-made category-specific image
        logger.warning(f"Placeholder image requested for {slot_id}/{option_label}")
        return None
