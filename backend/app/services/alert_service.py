"""
System Alert Service.

Sends failure/health alerts to the admin's personal Telegram chat,
independent of the SMM notification channel. Uses httpx directly
for minimal dependencies.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DUBAI_TZ = ZoneInfo("Asia/Dubai")


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_alert(title: str, details: dict | None = None, error: str | None = None) -> bool:
    """
    Send a system alert to the admin's personal Telegram chat.

    Args:
        title: Short alert title (e.g. "Content Generation Failed")
        details: Optional dict of key-value context to include
        error: Optional error message string

    Returns:
        True if sent successfully, False otherwise
    """
    bot_token = settings.telegram_bot_token
    chat_id = settings.telegram_alert_chat_id
    if not bot_token or not chat_id:
        logger.debug("Alert service not configured (missing bot token or alert chat ID)")
        return False

    now_str = datetime.now(DUBAI_TZ).strftime("%H:%M %d/%m/%Y")

    parts = [f"🚨 <b>{_escape_html(title)}</b>", ""]

    if details:
        for k, v in details.items():
            parts.append(f"<b>{_escape_html(str(k))}:</b> {_escape_html(str(v))}")
        parts.append("")

    if error:
        parts.append(f"❌ <b>Error:</b> {_escape_html(str(error)[:500])}")
        parts.append("")

    parts.append(f"🕐 {now_str} Dubai")

    message = "\n".join(parts)

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=15)

        if resp.status_code == 200:
            logger.info(f"Alert sent: {title}")
            return True
        else:
            logger.error(f"Alert delivery failed: {resp.status_code} {resp.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False
