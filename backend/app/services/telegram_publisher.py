"""
Telegram Publisher Service.

Publishes bilingual posts to Telegram channel using python-telegram-bot.
"""
import asyncio
import logging
import re
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
    image_data: Optional[str] = None  # Base64 encoded image
    # Keep EN fields for backwards compatibility (empty strings)
    title_en: str = ""
    body_en: str = ""
    album_images_data: Optional[list[str]] = None  # Additional base64 images for album


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

    CAPTION_LIMIT = 1024

    def _format_post_html(
        self,
        title: str,
        body: str,
        hashtags: list[str],
        language: str,
        max_length: int = 0,
    ) -> str:
        """
        Format post content for Telegram using HTML.

        Args:
            title: Post title
            body: Post body text
            hashtags: List of hashtags
            language: "en" or "ru"
            max_length: If > 0, truncate body to fit within this limit

        Returns:
            HTML-formatted message string
        """
        # Format hashtags
        hashtag_text = " ".join(hashtags) if hashtags else ""

        # Calculate overhead (everything except body)
        escaped_title = self._escape_html(title)
        title_line = f"<b>{escaped_title}</b>"
        channel_username = (settings.telegram_channel_id or "").lstrip("@")
        channel_line = f'Подписывайтесь на наш канал: <a href="https://t.me/{channel_username}">@{channel_username}</a>' if channel_username else ""

        # Build non-body parts to measure overhead
        overhead_parts = [title_line, ""]
        if hashtag_text:
            overhead_parts.extend(["", hashtag_text])
        if channel_line:
            overhead_parts.extend(["", channel_line])
        # +1 for the newline between title block and body
        overhead = len("\n".join(overhead_parts)) + 1  # +1 for body's leading \n

        sanitized_body = self._sanitize_telegram_html(body)

        # Truncate body if needed to fit within max_length (tag-aware)
        if max_length > 0 and (overhead + len(sanitized_body)) > max_length:
            available = max_length - overhead - 3  # 3 for "..."
            if available > 100:
                sanitized_body = self._truncate_html(sanitized_body, available)

        # Build the message
        message_parts = [title_line, "", sanitized_body]
        if hashtag_text:
            message_parts.extend(["", hashtag_text])
        if channel_line:
            message_parts.extend(["", channel_line])

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

    @staticmethod
    def _sanitize_telegram_html(text: str) -> str:
        """
        Sanitize HTML for Telegram, preserving allowed tags and escaping the rest.

        Allowed tags: b, i, u, s, code, pre, blockquote, a, tg-spoiler.
        All other angle-bracket sequences are escaped to &lt;/&gt;.
        Bare & signs are escaped to &amp; unless already part of an HTML entity.
        """
        # Allowed tag pattern — matches opening, closing, and self-closing variants.
        # For <a> we allow href="..." attribute; for blockquote we allow expandable attr.
        ALLOWED_TAG_RE = re.compile(
            r'^<(/?)(?:'
            r'b|i|u|s|code|pre|tg-spoiler'
            r'|blockquote(?:\s+expandable)?'
            r'|a(?:\s+href=["\']https?://[^"\'<>]*["\'])?'
            r')(/?)>$',
            re.IGNORECASE,
        )

        # First escape bare & (not already part of &amp; / &lt; / &gt; / &quot;)
        text = re.sub(r'&(?!(?:amp|lt|gt|quot);)', '&amp;', text)

        # Now walk through all <...> sequences and decide: keep or escape
        def replace_tag(m: re.Match) -> str:
            tag = m.group(0)
            if ALLOWED_TAG_RE.match(tag):
                return tag
            # Escape the angle brackets of disallowed tags
            return tag.replace('<', '&lt;').replace('>', '&gt;')

        return re.sub(r'<[^>]*>', replace_tag, text)

    @staticmethod
    def _truncate_html(html: str, max_chars: int) -> str:
        """
        Truncate HTML to at most max_chars visible characters, never cutting inside
        a tag, and close any tags left open after truncation.

        Appends '...' at the truncation point.
        """
        # Void/self-closing tags that never need a closing counterpart
        VOID_TAGS = {'br', 'hr', 'img', 'input'}

        open_tags: list[str] = []   # stack of tag names that need closing
        char_count = 0
        i = 0
        result_parts: list[str] = []
        truncated = False

        while i < len(html):
            if html[i] == '<':
                # Find end of tag
                end = html.find('>', i)
                if end == -1:
                    # Malformed — treat remainder as text
                    remaining = html[i:]
                    chars_needed = max_chars - char_count
                    if len(remaining) <= chars_needed:
                        result_parts.append(remaining)
                        char_count += len(remaining)
                    else:
                        result_parts.append(remaining[:chars_needed])
                        char_count = max_chars
                        truncated = True
                    break

                tag_text = html[i:end + 1]
                tag_inner = tag_text[1:-1].strip()

                # Determine tag name and whether it's a closing tag
                is_closing = tag_inner.startswith('/')
                tag_name = tag_inner.lstrip('/').split()[0].split('/')[0].lower()

                result_parts.append(tag_text)
                i = end + 1

                if tag_name in VOID_TAGS or tag_inner.endswith('/'):
                    pass  # self-closing, nothing to track
                elif is_closing:
                    # Pop from stack (remove last matching open tag)
                    for k in range(len(open_tags) - 1, -1, -1):
                        if open_tags[k] == tag_name:
                            open_tags.pop(k)
                            break
                else:
                    open_tags.append(tag_name)

            else:
                # Plain text character
                if char_count >= max_chars:
                    truncated = True
                    break
                result_parts.append(html[i])
                char_count += 1
                i += 1

                if char_count == max_chars and i < len(html):
                    # Check there's actually more content (non-tag) ahead
                    rest = html[i:]
                    has_more_text = bool(re.sub(r'<[^>]*>', '', rest).strip())
                    if has_more_text:
                        truncated = True
                        break

        if truncated:
            result_parts.append('...')

        # Close any still-open tags in reverse order
        for tag_name in reversed(open_tags):
            result_parts.append(f'</{tag_name}>')

        return ''.join(result_parts)

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
        image_data: Optional[str] = None,
    ) -> Optional[int]:
        """
        Send a message with photo to the channel.

        Args:
            text: HTML-formatted message text
            image_url: URL of the image to send
            image_local_path: Local path to image file
            image_data: Base64 encoded image data

        Returns:
            Message ID if successful
        """
        import base64
        from io import BytesIO

        photo = None
        photo_file = None

        # Determine photo source (priority: base64 > local file > URL)
        if image_data:
            # Decode base64 image
            try:
                image_bytes = base64.b64decode(image_data)
                photo_file = BytesIO(image_bytes)
                photo_file.name = "image.png"  # Telegram needs a filename
                photo = photo_file
                logger.info(f"Using base64 image ({len(image_bytes)} bytes)")
            except Exception as e:
                logger.error(f"Failed to decode base64 image: {e}")
        elif image_local_path:
            path = Path(image_local_path)
            if path.exists():
                photo = path.open("rb")
                logger.info(f"Using local file: {image_local_path}")
        elif image_url:
            photo = image_url
            logger.info(f"Using image URL: {image_url}")

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
                # Close file handles if we opened any
                if hasattr(photo, 'close'):
                    photo.close()
        else:
            # No image - send text only
            logger.info("No image available, sending text only")
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
            # Check if post has an image to determine caption limit
            has_image = content.image_data or content.image_url or content.image_local_path
            max_length = self.CAPTION_LIMIT if has_image else 0

            # Format Russian version (truncate body if needed for photo caption)
            text_ru = self._format_post_html(
                title=content.title_ru,
                body=content.body_ru,
                hashtags=content.hashtags,
                language="ru",
                max_length=max_length,
            )

            # Send Russian version with image
            message_id_ru = await self._send_photo_message(
                text=text_ru,
                image_url=content.image_url,
                image_local_path=content.image_local_path,
                image_data=content.image_data,
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

    async def publish_album(
        self,
        content: PostContent,
    ) -> PublishResult:
        """
        Publish a media group (album) to the Telegram channel.

        The first image carries the caption (formatted the same way as a single
        photo post). Additional images come from content.album_images_data.

        Args:
            content: PostContent with Russian content, primary image_data, and
                     optional album_images_data for extra images.

        Returns:
            PublishResult with message_id from the first message in the group.
        """
        import base64
        from io import BytesIO

        logger.info(f"Publishing album to channel {self.channel_id}")

        try:
            # Build caption for the first image (same rules as single-photo)
            text_ru = self._format_post_html(
                title=content.title_ru,
                body=content.body_ru,
                hashtags=content.hashtags,
                language="ru",
                max_length=self.CAPTION_LIMIT,
            )

            # --- Build the media list ---
            media: list[InputMediaPhoto] = []

            # First image: primary image_data carries the caption
            if content.image_data:
                try:
                    img_bytes = base64.b64decode(content.image_data)
                    buf = BytesIO(img_bytes)
                    buf.name = "image_0.png"
                    media.append(InputMediaPhoto(
                        media=buf,
                        caption=text_ru,
                        parse_mode=ParseMode.HTML,
                    ))
                    logger.info(f"Album primary image: {len(img_bytes)} bytes")
                except Exception as e:
                    logger.error(f"Failed to decode primary album image: {e}")

            # Additional images (no caption)
            if content.album_images_data:
                for idx, img_b64 in enumerate(content.album_images_data, start=1):
                    try:
                        img_bytes = base64.b64decode(img_b64)
                        buf = BytesIO(img_bytes)
                        buf.name = f"image_{idx}.png"
                        media.append(InputMediaPhoto(media=buf))
                        logger.info(f"Album image {idx}: {len(img_bytes)} bytes")
                    except Exception as e:
                        logger.warning(f"Skipping album image {idx}, decode error: {e}")

            if not media:
                # No images at all — fall back to a plain text message
                logger.warning("publish_album called with no images; falling back to text")
                message_id = await self._send_with_retry(
                    self.bot.send_message,
                    chat_id=self.channel_id,
                    text=text_ru,
                    parse_mode=ParseMode.HTML,
                )
                if not message_id:
                    return PublishResult(
                        success=False,
                        error="Failed to publish album (no images, text fallback also failed)",
                        channel_id=self.channel_id,
                    )
                return PublishResult(
                    success=True,
                    message_id_ru=message_id,
                    channel_id=self.channel_id,
                )

            # Send the album with retry logic
            last_error: Optional[str] = None
            messages = None

            for attempt in range(self.MAX_RETRIES):
                try:
                    messages = await self.bot.send_media_group(
                        chat_id=self.channel_id,
                        media=media,
                    )
                    break

                except RetryAfter as e:
                    wait_time = e.retry_after
                    logger.warning(f"Rate limited (album), waiting {wait_time}s")
                    await asyncio.sleep(wait_time)

                except TimedOut as e:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    logger.warning(
                        f"Timeout sending album, attempt {attempt + 1}/{self.MAX_RETRIES}, "
                        f"waiting {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    last_error = str(e)

                except TelegramError as e:
                    logger.error(f"Telegram error sending album: {e}")
                    last_error = str(e)
                    if "chat not found" in str(e).lower():
                        raise ValueError(f"Channel not found: {self.channel_id}")
                    if "bot was blocked" in str(e).lower():
                        raise ValueError("Bot was blocked by the channel")
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(wait_time)

            if not messages:
                return PublishResult(
                    success=False,
                    error=f"Failed to publish album after {self.MAX_RETRIES} attempts: {last_error}",
                    channel_id=self.channel_id,
                )

            message_id_ru = messages[0].message_id
            logger.info(f"Published album, first message_id={message_id_ru}")

            return PublishResult(
                success=True,
                message_id_ru=message_id_ru,
                channel_id=self.channel_id,
            )

        except ValueError as e:
            logger.error(f"Configuration error publishing album: {e}")
            return PublishResult(
                success=False,
                error=str(e),
                channel_id=self.channel_id,
            )
        except Exception as e:
            logger.error(f"Unexpected error publishing album: {e}")
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
