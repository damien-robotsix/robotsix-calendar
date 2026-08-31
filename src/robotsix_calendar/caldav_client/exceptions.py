"""Typed exception hierarchy for calendar agent errors.

Modeled on ``caldav/lib/error.py`` — each exception subclass carries a
static ``_code`` string so callers can ``except`` on type rather than
string-matching ``exc.code``.

"""

from __future__ import annotations


class CalendarError(Exception):
    """Base exception for all calendar agent errors."""

    _code: str = ""

    def __init__(self, message: str) -> None:
        self.code = self._code or type(self).__name__
        self.message = message
        super().__init__(message)


class NotFoundError(CalendarError):
    """Resource not found."""

    _code = "not_found"


class AuthError(CalendarError):
    """Authentication / authorization failure."""

    _code = "auth_failed"


class RateLimitError(CalendarError):
    """Rate-limited (HTTP 429)."""

    _code = "rate_limited"


class ConflictError(CalendarError):
    """Etag mismatch / conflict."""

    _code = "conflict"


class CalDAVError(CalendarError):
    """Generic CalDAV error (catch-all for transport/protocol errors)."""

    _code = "caldav_error"


class AgentLogicError(CalendarError):
    """Agent orchestration logic error (not a server error)."""

    _code = "agent_logic_error"
