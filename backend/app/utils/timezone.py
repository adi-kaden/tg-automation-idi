from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings

settings = get_settings()

# Dubai timezone
DUBAI_TZ = ZoneInfo(settings.app_timezone)
UTC_TZ = ZoneInfo("UTC")

# Daily posting slots (Dubai time)
POSTING_SLOTS = [
    {"number": 1, "time": "08:00", "content_type": "real_estate"},
    {"number": 2, "time": "12:00", "content_type": "general_dubai"},
    {"number": 3, "time": "16:00", "content_type": "real_estate"},
    {"number": 4, "time": "20:00", "content_type": "general_dubai"},
    {"number": 5, "time": "00:00", "content_type": "general_dubai"},
]

# Approval deadline offset (minutes before scheduled time)
APPROVAL_DEADLINE_MINUTES = 30


def now_dubai() -> datetime:
    """Get current datetime in Dubai timezone."""
    return datetime.now(DUBAI_TZ)


def now_utc() -> datetime:
    """Get current datetime in UTC."""
    return datetime.now(UTC_TZ)


def to_dubai(dt: datetime) -> datetime:
    """Convert datetime to Dubai timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(DUBAI_TZ)


def to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DUBAI_TZ)
    return dt.astimezone(UTC_TZ)


def dubai_date_to_slot_datetime(
    slot_date: date,
    slot_time: str,
) -> datetime:
    """
    Convert a date and time string (e.g., "08:00") to a full datetime in UTC.
    """
    hour, minute = map(int, slot_time.split(":"))

    # Handle midnight (00:00) - it belongs to the next day
    if hour == 0 and minute == 0:
        slot_date = slot_date + timedelta(days=1)

    dubai_dt = datetime(
        year=slot_date.year,
        month=slot_date.month,
        day=slot_date.day,
        hour=hour,
        minute=minute,
        tzinfo=DUBAI_TZ,
    )
    return to_utc(dubai_dt)


def get_approval_deadline(scheduled_at: datetime) -> datetime:
    """
    Calculate the approval deadline for a slot.
    Default is 30 minutes before scheduled time.
    """
    return scheduled_at - timedelta(minutes=APPROVAL_DEADLINE_MINUTES)


def get_today_slots() -> list[dict]:
    """
    Get all posting slots for today with their scheduled times in UTC.
    """
    today = now_dubai().date()
    slots = []

    for slot_info in POSTING_SLOTS:
        scheduled_at = dubai_date_to_slot_datetime(today, slot_info["time"])
        approval_deadline = get_approval_deadline(scheduled_at)

        slots.append({
            "slot_number": slot_info["number"],
            "scheduled_time": slot_info["time"],
            "content_type": slot_info["content_type"],
            "scheduled_at": scheduled_at,
            "approval_deadline": approval_deadline,
            "scheduled_date": today,
        })

    return slots


def format_dubai_time(dt: datetime) -> str:
    """Format datetime as Dubai time string (e.g., '08:00 AM')."""
    dubai_dt = to_dubai(dt)
    return dubai_dt.strftime("%I:%M %p")


def format_dubai_date(dt: datetime) -> str:
    """Format datetime as Dubai date string (e.g., 'Feb 23, 2026')."""
    dubai_dt = to_dubai(dt)
    return dubai_dt.strftime("%b %d, %Y")


def format_dubai_datetime(dt: datetime) -> str:
    """Format datetime as full Dubai datetime string."""
    dubai_dt = to_dubai(dt)
    return dubai_dt.strftime("%b %d, %Y %I:%M %p")
