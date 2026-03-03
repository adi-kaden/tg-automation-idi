"""
Image Generator using Google Imagen API.

Generates images for Telegram posts based on prompts.
"""
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

    def _enhance_prompt(self, base_prompt: str, category: str) -> str:
        """Enhance the image prompt with style guidance."""

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
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Generate an image for a post option using Imagen 4.0.

        Args:
            prompt: Base image prompt from content generator
            category: Content category for style guidance
            slot_id: Content slot ID for file naming
            option_label: Option label (A/B) for file naming

        Returns:
            Tuple of (image_url, local_path) - url may be None if only local storage
        """
        enhanced_prompt = self._enhance_prompt(prompt, category)

        logger.info(f"Generating image for slot {slot_id} option {option_label}")

        try:
            # Generate image using Imagen 4.0
            response = self.client.models.generate_images(
                model=self.model,
                prompt=enhanced_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                    safety_filter_level="BLOCK_LOW_AND_ABOVE",
                ),
            )

            if response.generated_images and len(response.generated_images) > 0:
                img = response.generated_images[0]

                # Save the image locally
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{slot_id}_{option_label}_{timestamp}.png"
                filepath = self.output_dir / filename

                # Get image bytes and save
                image_bytes = img.image.image_bytes
                filepath.write_bytes(image_bytes)

                logger.info(f"Image saved to {filepath} ({len(image_bytes)} bytes)")
                return (None, str(filepath))

            logger.warning("Imagen did not return any images")
            return (None, None)

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            # Don't raise - image is optional, post can go without
            return (None, None)

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
