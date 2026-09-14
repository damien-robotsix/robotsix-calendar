"""Typed exception hierarchy for calendar agent errors.

Modeled on ``caldav/lib/error.py`` — each exception subclass carries a
static ``code`` string so callers can ``except`` on type rather than
string-matching ``exc.code``.

The hierarchy is re-based on :class:`robotsix_http.fastapi.DomainError`, so
each subclass also declares the ``status_code`` the shared FastAPI exception
handler renders it with, converging the service on the canonical nested
error envelope ``{"error": {"code": ..., "detail": ...}}``.
"""

from __future__ import annotations

from robotsix_http.fastapi import DomainError


class CalendarError(DomainError):
    """Base exception for all calendar agent errors."""

    status_code = 500
    code = "calendar_error"


class NotFoundError(CalendarError):
    """Resource not found."""

    status_code = 404
    code = "not_found"


class AuthError(CalendarError):
    """Authentication / authorization failure."""

    status_code = 401
    code = "auth_failed"


class RateLimitError(CalendarError):
    """Rate-limited (HTTP 429)."""

    status_code = 429
    code = "rate_limited"


class ConflictError(CalendarError):
    """Etag mismatch / conflict."""

    status_code = 409
    code = "conflict"


class CalDAVError(CalendarError):
    """Generic CalDAV error (catch-all for transport/protocol errors)."""

    status_code = 502
    code = "caldav_error"


class AgentLogicError(CalendarError):
    """Agent orchestration logic error (not a server error)."""

    status_code = 500
    code = "agent_logic_error"
