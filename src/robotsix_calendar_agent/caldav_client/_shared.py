"""Shared infrastructure for the caldav_client package.

Dataclasses, exceptions, and the ``_wrap_caldav_op`` decorator live here
so that domain-specific mixin modules can import them without creating
circular dependencies on ``__init__.py``.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, cast

from opentelemetry import trace
from opentelemetry.trace import Span
from robotsix_http.retry import RetryConfig, call_with_retry

from .exceptions import (
    AuthError,
    CalDAVError,
    CalendarError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)

_tracer = trace.get_tracer(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


class _CalDavClientProtocol(Protocol):
    """Structural contract the concrete ``CalDavClient`` provides to mixins.

    Declared once here as the single source of truth for the host-class
    members each domain mixin relies on. Domain mixins reference this
    Protocol (under ``TYPE_CHECKING``) instead of re-declaring copy-pasted
    stub blocks, so a signature change on ``CalDavClient`` that drifts from
    the contract is caught by mypy as an incompatible override rather than
    silently diverging across files.
    """

    _caldav: Any

    @staticmethod
    def _escape_text(value: str) -> str: ...

    @staticmethod
    def _ical_dt(name: str, value: str) -> str: ...

    def _iter_calendars(self, calendar_id: str = "") -> list[Any]: ...

    def _get_calendar(self, calendar_id: str = "") -> Any: ...

    def _get_addressbook(self, addressbook_id: str = "") -> Any: ...


@dataclass(kw_only=True)
class CalendarEvent:
    """Calendar event data transferred to/from the CalDAV server.

    Attributes:
        uid: Server-assigned unique identifier (empty for new events).
        summary: Short summary / title.
        description: Longer description (optional).
        location: Event location (optional).
        dtstart: Start time in ISO 8601 format.
        dtend: End time in ISO 8601 format.
        calendar_id: Calendar name the event belongs to (optional).
    """

    uid: str = ""
    summary: str
    description: str = ""
    location: str = ""
    dtstart: str  # ISO 8601
    dtend: str  # ISO 8601
    calendar_id: str = ""


@dataclass(kw_only=True)
class Task:
    """Represents a single VTODO task from a CalDAV calendar.

    Attributes:
        uid: Server-assigned unique identifier (empty for new tasks).
        summary: Short summary / title.
        description: Longer description (optional).
        dtstart: When the task starts (optional, ISO 8601).
        due: Task due date/time (VTODO DUE field, optional, ISO 8601).
        status: Task status — e.g. NEEDS-ACTION, IN-PROCESS, COMPLETED,
            CANCELLED.
        calendar_id: Calendar name the task belongs to (optional).
    """

    uid: str = ""
    summary: str
    description: str = ""
    dtstart: str = ""  # ISO 8601
    due: str = ""  # ISO 8601 — VTODO DUE field
    status: str = ""  # e.g. NEEDS-ACTION
    calendar_id: str = ""


@dataclass(kw_only=True)
class Contact:
    """Contact data transferred to/from the CardDAV server.

    Attributes:
        uid: Server-assigned unique identifier (empty for new contacts).
        full_name: Display name.
        email: Email address (optional).
        phone: Phone number (optional).
        address: Postal address (optional).
        addressbook_id: Address book name the contact belongs to (optional).
    """

    uid: str = ""
    full_name: str
    email: str = ""
    phone: str = ""
    address: str = ""
    addressbook_id: str = ""


def _is_transient_exception(exc: BaseException) -> bool:
    """Return True for exceptions that may succeed on retry."""
    msg = str(exc).lower()
    # Connection-level / timeout errors from requests/httpx
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    # Socket-level errors wrapped in generic Exception by caldav
    return any(
        word in msg
        for word in (
            "connection refused",
            "connection reset",
            "timeout",
            "timed out",
            "name or service not known",
            "temporary failure",
            "econnrefused",
            "econnreset",
            "eof",
            "broken pipe",
        )
    )


def _comp_text(comp: Any, name: str) -> str:
    """Extract a text value from an iCalendar component property."""
    value = comp.get(name)
    return str(value) if value is not None else ""


def _comp_dt(comp: Any, name: str) -> str:
    """Extract a datetime value from an iCalendar component property."""
    import datetime

    value = comp.get(name)
    if value is None:
        return ""
    moment = getattr(value, "dt", value)
    # datetime is a subclass of date — both serialise via isoformat().
    if isinstance(moment, datetime.date):
        return moment.isoformat()
    return str(moment)


def _unescape_text(value: str) -> str:
    r"""Reverse the escaping applied by ``_escape_text``.

    Uses a placeholder for ``\\\\`` to avoid creating spurious
    escape sequences during sequential replacement.  Restores
    ``\\n`` → ``\n``, ``\\;`` → ``;``, ``\\,`` → ``,``,
    ``\\\\`` → ``\\``.
    """
    if not value:
        return value
    # Replace \\ with a sentinel to avoid it forming spurious
    # \; or \, sequences in later steps.
    sentinel = "\x00"
    result = value.replace("\\\\", sentinel)
    result = result.replace("\\n", "\n")
    result = result.replace("\\;", ";")
    result = result.replace("\\,", ",")
    result = result.replace(sentinel, "\\")
    return result


def _record_and_raise(
    exc: Exception,
    error_code: str,
    target_exc_cls: type[CalendarError],
    message: str,
    span: Span,
) -> None:
    span.set_attribute("caldav.error_code", error_code)
    span.set_attribute("error", True)
    span.record_exception(exc)
    raise target_exc_cls(message) from exc


def _wrap_caldav_op(op_name: str) -> Callable[[_F], _F]:
    """Wrap a method with retry logic and standard CalDAV error handling.

    Transient network errors (connection refused, timeout, DNS
    failures) are retried up to 3 times with exponential backoff
    before being converted to a :class:`CalDAVError`.

    :class:`CalendarError` exceptions are re-raised as-is.
    All other exceptions are logged and wrapped in a
    :class:`CalDAVError`.
    """

    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            with _tracer.start_as_current_span(f"caldav.{op_name}") as span:
                span.set_attribute("caldav.op", op_name)
                try:
                    return call_with_retry(
                        lambda: func(self, *args, **kwargs),
                        config=RetryConfig(max_retries=3),
                        is_transient_fn=_is_transient_exception,
                        what=f"caldav.{op_name}",
                    )
                except CalendarError:
                    raise
                except self._caldav.lib.error.NotFoundError as exc:
                    _record_and_raise(
                        exc, "not_found", NotFoundError, f"{op_name}: {exc}", span
                    )
                except self._caldav.lib.error.RateLimitError as exc:
                    _record_and_raise(
                        exc, "rate_limited", RateLimitError, f"{op_name}: {exc}", span
                    )
                except self._caldav.lib.error.EtagMismatchError as exc:
                    _record_and_raise(
                        exc, "conflict", ConflictError, f"{op_name}: {exc}", span
                    )
                except self._caldav.lib.error.AuthorizationError as exc:
                    _record_and_raise(
                        exc, "auth_failed", AuthError, f"{op_name}: {exc}", span
                    )
                except Exception as exc:
                    logger.exception("%s failed: %s", func.__name__, exc)
                    _record_and_raise(
                        exc,
                        "caldav_error",
                        CalDAVError,
                        f"Failed to {op_name}: {exc}",
                        span,
                    )

        return cast(_F, wrapper)

    return decorator
