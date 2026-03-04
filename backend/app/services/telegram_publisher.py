"""
Telegram Publisher Service.

Publishes bilingual posts to Telegram channel using python-telegram-bot.
"""
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from telegram import Bot, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, TimedOut

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PublishResult:
    """Result of publishing a post to Telegram."""
    success: bool
    message_id_en: Optional[int] = None
    message_id_ru: Optional[int] = None
    error: Optional[str] = None
    channel_id: Optional[str] = None


@dataclass
class PostContent:
    """Content to be published (Russian-only)."""
    title_ru: str
    body_ru: str
    hashtags: list[str]
    image_url: Optional[str] = None
    image_local_path: Optional[str] = None
    # Keep EN fields for backwards compatibility (empty strings)
    title_en: str = ""
    body_en: str = ""


class TelegramPublisher:
    """
    Publish posts to Telegram channel.

    Handles Russian content, image uploads, and retry logic.
    """

    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 2  # seconds

    def __init__(self):
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not configured")
        if not settings.telegram_channel_id:
            raise ValueError("TELEGRAM_CHANNEL_ID not configured")

        self.bot = Bot(token=settings.telegram_bot_token)
        self.channel_id = settings.telegram_channel_id

    def _format_post_html(
        self,
        title: str,
        body: str,
        hashtags: list[str],
        language: str,
    ) -> str:
        """
        Format post content for Telegram using HTML.

        Args:
            title: Post title
            body: Post body text
            hashtags: List of hashtags
            language: "en" or "ru"

        Returns:
            HTML-formatted message string
        """
        # Format hashtags
        hashtag_text = " ".join(hashtags) if hashtags else ""

        # Build the message with HTML formatting
        # Using <b> for bold title
        message_parts = [
            f"<b>{self._escape_html(title)}</b>",
            "",
            self._escape_html(body),
        ]

        if hashtag_text:
            message_parts.extend(["", hashtag_text])

        return "\n".join(message_parts)

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters for Telegram."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    async def _send_with_retry(
        self,
        send_func,
        *args,
        **kwargs,
    ) -> Optional[int]:
        """
        Execute a send function with retry logic.

        Args:
            send_func: Async function to call
            *args, **kwargs: Arguments to pass to send_func

        Returns:
            Message ID if successful, None otherwise
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                message = await send_func(*args, **kwargs)
                return message.message_id

            except RetryAfter as e:
                # Telegram rate limit - wait the specified time
                wait_time = e.retry_after
                logger.warning(f"Rate limited by Telegram, waiting {wait_time}s")
                await asyncio.sleep(wait_time)

            except TimedOut as e:
                # Timeout - retry with exponential backoff
                wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                logger.warning(f"Telegram timeout, attempt {attempt + 1}/{self.MAX_RETRIES}, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
                last_error = str(e)

            except TelegramError as e:
                logger.error(f"Telegram error: {e}")
                last_error = str(e)

                # Don't retry for certain errors
                if "chat not found" in str(e).lower():
                    raise ValueError(f"Channel not found: {self.channel_id}")
                if "bot was blocked" in str(e).lower():
                    raise ValueError("Bot was blocked by the channel")

                # Retry for other errors
                wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                await asyncio.sleep(wait_time)

        logger.error(f"Failed after {self.MAX_RETRIES} attempts: {last_error}")
        return None

    async def _send_photo_message(
        self,
        text: str,
        image_url: Optional[str] = None,
        image_local_path: Optional[str] = None,
    ) -> Optional[int]:
        """
        Send a message with photo to the channel.

        Args:
            text: HTML-formatted message text
            image_url: URL of the image to send
            image_local_path: Local path to image file

        Returns:
            Message ID if successful
        """
        photo = None

        # Determine photo source
        if image_local_path:
            path = Path(image_local_path)
            if path.exists():
                photo = path.open("rb")
        elif image_url:
            photo = image_url

        if photo:
            try:
                message_id = await self._send_with_retry(
                    self.bot.send_photo,
                    chat_id=self.channel_id,
                    photo=photo,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                )
                return message_id
            finally:
                # Close file handle if we opened one
                if image_local_path and hasattr(photo, 'close'):
                    photo.close()
        else:
            # No image - send text only
            return await self._send_with_retry(
                self.bot.send_message,
                chat_id=self.channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )

    async def publish_post(
        self,
        content: PostContent,
        publish_both_languages: bool = False,  # Deprecated, kept for compatibility
    ) -> PublishResult:
        """
        Publish a post to the Telegram channel (Russian only).

        Args:
            content: PostContent with Russian content and optional image
            publish_both_languages: Deprecated, ignored (always publishes Russian only)

        Returns:
            PublishResult with message ID and status
        """
        logger.info(f"Publishing Russian post to channel {self.channel_id}")

        try:
            # Format Russian version
            text_ru = self._format_post_html(
                title=content.title_ru,
                body=content.body_ru,
                hashtags=content.hashtags,
                language="ru",
            )

            # Send Russian version with image
            message_id_ru = await self._send_photo_message(
                text=text_ru,
                image_url=content.image_url,
                image_local_path=content.image_local_path,
            )

            if not message_id_ru:
                return PublishResult(
                    success=False,
                    error="Failed to publish Russian post",
                    channel_id=self.channel_id,
                )

            logger.info(f"Published RU post, message_id={message_id_ru}")

            return PublishResult(
                success=True,
                message_id_en=None,  # No English version
                message_id_ru=message_id_ru,
                channel_id=self.channel_id,
            )

        except ValueError as e:
            # Configuration errors
            logger.error(f"Configuration error: {e}")
            return PublishResult(
                success=False,
                error=str(e),
                channel_id=self.channel_id,
            )
        except Exception as e:
            logger.error(f"Unexpected error publishing post: {e}")
            return PublishResult(
                success=False,
                error=str(e),
                channel_id=self.channel_id,
            )

    async def publish_single_language(
        self,
        title: str,
        body: str,
        hashtags: list[str],
        language: str,
        image_url: Optional[str] = None,
        image_local_path: Optional[str] = None,
    ) -> PublishResult:
        """
        Publish a single-language post.

        Args:
            title: Post title
            body: Post body
            hashtags: List of hashtags
            language: "en" or "ru"
            image_url: Optional image URL
            image_local_path: Optional local image path

        Returns:
            PublishResult with message ID and status
        """
        logger.info(f"Publishing {language.upper()} post to channel {self.channel_id}")

        try:
            text = self._format_post_html(
                title=title,
                body=body,
                hashtags=hashtags,
                language=language,
            )

            message_id = await self._send_photo_message(
                text=text,
                image_url=image_url,
                image_local_path=image_local_path,
            )

            if message_id:
                result_kwargs = {
                    "success": True,
                    "channel_id": self.channel_id,
                }
                if language == "en":
                    result_kwargs["message_id_en"] = message_id
                else:
                    result_kwargs["message_id_ru"] = message_id

                return PublishResult(**result_kwargs)
            else:
                return PublishResult(
                    success=False,
                    error=f"Failed to publish {language.upper()} version",
                    channel_id=self.channel_id,
                )

        except Exception as e:
            logger.error(f"Error publishing {language} post: {e}")
            return PublishResult(
                success=False,
                error=str(e),
                channel_id=self.channel_id,
            )

    async def delete_message(self, message_id: int) -> bool:
        """
        Delete a message from the channel.

        Args:
            message_id: Telegram message ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            await self.bot.delete_message(
                chat_id=self.channel_id,
                message_id=message_id,
            )
            logger.info(f"Deleted message {message_id} from {self.channel_id}")
            return True
        except TelegramError as e:
            logger.error(f"Failed to delete message {message_id}: {e}")
            return False

    async def get_channel_info(self) -> Optional[dict]:
        """
        Get information about the configured channel.

        Returns:
            Dict with channel info or None if error
        """
        try:
            chat = await self.bot.get_chat(self.channel_id)
            return {
                "id": chat.id,
                "title": chat.title,
                "username": chat.username,
                "type": chat.type,
                "member_count": getattr(chat, "member_count", None),
            }
        except TelegramError as e:
            logger.error(f"Failed to get channel info: {e}")
            return None

    async def test_connection(self) -> tuple[bool, str]:
        """
        Test the bot connection and channel access.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Test bot is valid
            bot_info = await self.bot.get_me()
            logger.info(f"Bot connected: @{bot_info.username}")

            # Test channel access
            chat = await self.bot.get_chat(self.channel_id)
            logger.info(f"Channel accessible: {chat.title}")

            # Check if bot can post
            member = await self.bot.get_chat_member(self.channel_id, bot_info.id)
            can_post = member.status in ["administrator", "creator"]

            if can_post:
                return True, f"Connected to @{bot_info.username}, channel: {chat.title}"
            else:
                return False, f"Bot is not an administrator in {chat.title}"

        except TelegramError as e:
            return False, f"Connection failed: {e}"
