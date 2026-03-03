"""
SMM Notification Service.

Sends notifications to the SMM specialist via Telegram DM.
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DUBAI_TZ = ZoneInfo("Asia/Dubai")


class NotificationType(str, Enum):
    """Types of notifications that can be sent."""
    OPTIONS_READY = "options_ready"
    AUTO_SELECTED = "auto_selected"
    PUBLISH_SUCCESS = "publish_success"
    PUBLISH_FAILED = "publish_failed"
    GENERATION_FAILED = "generation_failed"
    DAILY_SUMMARY = "daily_summary"


@dataclass
class NotificationResult:
    """Result of sending a notification."""
    success: bool
    message_id: Optional[int] = None
    error: Optional[str] = None


class SMMNotificationService:
    """
    Send notifications to SMM specialist via Telegram.

    Uses the configured TELEGRAM_SMM_CHAT_ID to send direct messages
    about content ready for review, auto-selections, and failures.
    """

    def __init__(self):
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not configured")
        if not settings.telegram_smm_chat_id:
            raise ValueError("TELEGRAM_SMM_CHAT_ID not configured")

        self.bot = Bot(token=settings.telegram_bot_token)
        self.smm_chat_id = settings.telegram_smm_chat_id

    async def _send_message(
        self,
        text: str,
        parse_mode: str = ParseMode.HTML,
        disable_notification: bool = False,
    ) -> NotificationResult:
        """
        Send a message to the SMM chat.

        Args:
            text: HTML-formatted message
            parse_mode: Message parse mode
            disable_notification: If True, send silently

        Returns:
            NotificationResult with success status
        """
        try:
            message = await self.bot.send_message(
                chat_id=self.smm_chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )
            logger.info(f"Notification sent to SMM: message_id={message.message_id}")
            return NotificationResult(success=True, message_id=message.message_id)

        except TelegramError as e:
            logger.error(f"Failed to send notification: {e}")
            return NotificationResult(success=False, error=str(e))

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    async def notify_options_ready(
        self,
        slot_id: str,
        scheduled_time: str,
        content_type: str,
        options_count: int,
        minutes_until_deadline: int,
        dashboard_url: Optional[str] = None,
    ) -> NotificationResult:
        """
        Notify SMM that content options are ready for review.

        Args:
            slot_id: The content slot ID
            scheduled_time: The scheduled publish time (e.g., "08:00")
            content_type: Type of content (real_estate, general_dubai)
            options_count: Number of options generated
            minutes_until_deadline: Minutes until auto-selection
            dashboard_url: Optional URL to the approval page

        Returns:
            NotificationResult
        """
        content_label = "Real Estate" if content_type == "real_estate" else "Dubai Trending"

        message_parts = [
            "📝 <b>Content Ready for Review</b>",
            "",
            f"⏰ <b>Slot:</b> {scheduled_time}",
            f"📂 <b>Type:</b> {content_label}",
            f"📄 <b>Options:</b> {options_count} posts generated",
            f"⏳ <b>Deadline:</b> {minutes_until_deadline} minutes",
            "",
            "Please review and select an option before the deadline.",
        ]

        if dashboard_url:
            message_parts.append("")
            message_parts.append(f"🔗 <a href=\"{dashboard_url}\">Review Options</a>")

        return await self._send_message("\n".join(message_parts))

    async def notify_auto_selected(
        self,
        slot_id: str,
        scheduled_time: str,
        content_type: str,
        selected_option: str,
        confidence: float,
        reasoning: str,
    ) -> NotificationResult:
        """
        Notify SMM that auto-selection has occurred.

        Args:
            slot_id: The content slot ID
            scheduled_time: The scheduled publish time
            content_type: Type of content
            selected_option: Which option was selected (A or B)
            confidence: AI confidence score (0-1)
            reasoning: Brief explanation for the selection

        Returns:
            NotificationResult
        """
        content_label = "Real Estate" if content_type == "real_estate" else "Dubai Trending"
        confidence_pct = int(confidence * 100)

        # Truncate reasoning if too long
        if len(reasoning) > 200:
            reasoning = reasoning[:197] + "..."

        message_parts = [
            "🤖 <b>Auto-Selection Completed</b>",
            "",
            f"⏰ <b>Slot:</b> {scheduled_time}",
            f"📂 <b>Type:</b> {content_label}",
            f"✅ <b>Selected:</b> Option {selected_option}",
            f"📊 <b>Confidence:</b> {confidence_pct}%",
            "",
            f"<i>{self._escape_html(reasoning)}</i>",
            "",
            "No manual selection was made before the deadline.",
        ]

        return await self._send_message("\n".join(message_parts))

    async def notify_publish_success(
        self,
        slot_id: str,
        scheduled_time: str,
        title: str,
        selected_by: str,
        message_id_en: Optional[int] = None,
        message_id_ru: Optional[int] = None,
    ) -> NotificationResult:
        """
        Notify SMM of successful publication.

        Args:
            slot_id: The content slot ID
            scheduled_time: The scheduled publish time
            title: Post title
            selected_by: Who selected the option (human/ai)
            message_id_en: Telegram message ID for English post
            message_id_ru: Telegram message ID for Russian post

        Returns:
            NotificationResult
        """
        selector_label = "You" if selected_by == "human" else "AI"

        # Truncate title if too long
        if len(title) > 100:
            title = title[:97] + "..."

        message_parts = [
            "✅ <b>Post Published Successfully</b>",
            "",
            f"⏰ <b>Slot:</b> {scheduled_time}",
            f"📝 <b>Title:</b> {self._escape_html(title)}",
            f"👤 <b>Selected by:</b> {selector_label}",
        ]

        if message_id_en:
            message_parts.append(f"🇬🇧 <b>EN Message ID:</b> {message_id_en}")
        if message_id_ru:
            message_parts.append(f"🇷🇺 <b>RU Message ID:</b> {message_id_ru}")

        # Send silently for successful publishes to avoid notification fatigue
        return await self._send_message(
            "\n".join(message_parts),
            disable_notification=True,
        )

    async def notify_publish_failed(
        self,
        slot_id: str,
        scheduled_time: str,
        error_message: str,
        retry_count: int = 0,
    ) -> NotificationResult:
        """
        Notify SMM of publication failure.

        Args:
            slot_id: The content slot ID
            scheduled_time: The scheduled publish time
            error_message: The error that occurred
            retry_count: Number of retry attempts made

        Returns:
            NotificationResult
        """
        message_parts = [
            "❌ <b>Publication Failed</b>",
            "",
            f"⏰ <b>Slot:</b> {scheduled_time}",
            f"🔄 <b>Retries:</b> {retry_count}",
            "",
            f"<b>Error:</b> {self._escape_html(error_message[:200])}",
            "",
            "⚠️ Manual intervention may be required.",
        ]

        return await self._send_message("\n".join(message_parts))

    async def notify_generation_failed(
        self,
        slot_id: str,
        scheduled_time: str,
        content_type: str,
        error_message: str,
    ) -> NotificationResult:
        """
        Notify SMM of content generation failure.

        Args:
            slot_id: The content slot ID
            scheduled_time: The scheduled publish time
            content_type: Type of content
            error_message: The error that occurred

        Returns:
            NotificationResult
        """
        content_label = "Real Estate" if content_type == "real_estate" else "Dubai Trending"

        message_parts = [
            "⚠️ <b>Content Generation Failed</b>",
            "",
            f"⏰ <b>Slot:</b> {scheduled_time}",
            f"📂 <b>Type:</b> {content_label}",
            "",
            f"<b>Error:</b> {self._escape_html(error_message[:200])}",
            "",
            "Consider running manual regeneration or adding more source articles.",
        ]

        return await self._send_message("\n".join(message_parts))

    async def notify_daily_summary(
        self,
        date: str,
        total_slots: int,
        published: int,
        pending_review: int,
        auto_selected: int,
        failed: int,
    ) -> NotificationResult:
        """
        Send daily summary notification.

        Args:
            date: The date for the summary
            total_slots: Total slots for the day
            published: Number published
            pending_review: Number awaiting review
            auto_selected: Number auto-selected by AI
            failed: Number that failed

        Returns:
            NotificationResult
        """
        message_parts = [
            f"📊 <b>Daily Content Summary - {date}</b>",
            "",
            f"📅 <b>Total Slots:</b> {total_slots}",
            f"✅ <b>Published:</b> {published}",
            f"🤖 <b>Auto-selected:</b> {auto_selected}",
            f"⏳ <b>Pending Review:</b> {pending_review}",
        ]

        if failed > 0:
            message_parts.append(f"❌ <b>Failed:</b> {failed}")

        return await self._send_message("\n".join(message_parts))

    async def test_connection(self) -> tuple[bool, str]:
        """
        Test the notification connection.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Test bot is valid
            bot_info = await self.bot.get_me()

            # Test we can send to SMM chat
            result = await self._send_message(
                "🔔 <b>Test Notification</b>\n\nSMM notification system is working correctly.",
                disable_notification=True,
            )

            if result.success:
                return True, f"Connected via @{bot_info.username}, test message sent"
            else:
                return False, f"Bot connected but message failed: {result.error}"

        except TelegramError as e:
            return False, f"Connection failed: {e}"


# Convenience function for use in tasks
async def send_notification(
    notification_type: NotificationType,
    **kwargs,
) -> NotificationResult:
    """
    Send a notification of the specified type.

    This is a convenience wrapper that handles the case where
    notifications are not configured (returns silently).

    Args:
        notification_type: Type of notification to send
        **kwargs: Arguments for the specific notification method

    Returns:
        NotificationResult (success=True if not configured)
    """
    if not settings.telegram_smm_chat_id:
        logger.debug("SMM notifications not configured, skipping")
        return NotificationResult(success=True, error="Not configured")

    try:
        service = SMMNotificationService()

        method_map = {
            NotificationType.OPTIONS_READY: service.notify_options_ready,
            NotificationType.AUTO_SELECTED: service.notify_auto_selected,
            NotificationType.PUBLISH_SUCCESS: service.notify_publish_success,
            NotificationType.PUBLISH_FAILED: service.notify_publish_failed,
            NotificationType.GENERATION_FAILED: service.notify_generation_failed,
            NotificationType.DAILY_SUMMARY: service.notify_daily_summary,
        }

        method = method_map.get(notification_type)
        if not method:
            return NotificationResult(success=False, error=f"Unknown notification type: {notification_type}")

        return await method(**kwargs)

    except ValueError as e:
        # Not configured
        logger.debug(f"Notifications not configured: {e}")
        return NotificationResult(success=True, error=str(e))
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return NotificationResult(success=False, error=str(e))
