"""
Detect transient Postgres errors that should trigger a Celery retry
rather than a permanent task failure + Telegram spam.

Covers the "database system is in recovery mode" class of errors that
happen during Supabase/Postgres restarts, failovers, and brief network
hiccups — all of which resolve on their own within seconds to minutes.
"""
from __future__ import annotations

from sqlalchemy.exc import (
    DBAPIError,
    DisconnectionError,
    InterfaceError,
    OperationalError,
)

# Postgres SQLSTATEs that indicate transient, self-resolving conditions.
#   57P01 admin_shutdown
#   57P02 crash_shutdown
#   57P03 cannot_connect_now        <-- "database system is in recovery mode"
#   08xxx connection_exception family
_TRANSIENT_SQLSTATES = {
    "57P01", "57P02", "57P03",
    "08000", "08001", "08003", "08004", "08006", "08007", "08P01",
}

# Substring markers used as a fallback when SQLSTATE is unavailable
# (e.g. the connection died before the server sent a code).
_TRANSIENT_MARKERS = (
    "database system is in recovery mode",
    "database system is starting up",
    "database system is shutting down",
    "connection reset",
    "connection refused",
    "server closed the connection",
    "connection has been closed",
    "terminating connection due to administrator command",
    "ssl connection has been closed unexpectedly",
    "connection is closed",
    "cannot perform operation: another operation is in progress",
)


def is_transient_db_error(exc: BaseException | None) -> bool:
    """
    Return True if ``exc`` represents a transient DB condition worth retrying.

    Recognised cases:
      * SQLAlchemy DisconnectionError / InterfaceError (driver lost the link)
      * OperationalError / DBAPIError whose SQLSTATE is in the transient set
      * Any exception whose message contains a known transient marker
    """
    if exc is None:
        return False

    if isinstance(exc, (DisconnectionError, InterfaceError)):
        return True

    if isinstance(exc, (OperationalError, DBAPIError)):
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
        if sqlstate and sqlstate in _TRANSIENT_SQLSTATES:
            return True

    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


def transient_retry_countdown(attempt: int, base: int = 30, cap: int = 300) -> int:
    """Exponential backoff for Postgres retries: 30s, 60s, 120s, 240s, 300s."""
    return min(base * (2 ** max(attempt, 0)), cap)
