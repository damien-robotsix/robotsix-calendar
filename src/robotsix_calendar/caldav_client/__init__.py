"""CalDAV/CardDAV client wrapper for Radicale.

Typed, self-contained module wrapping the ``caldav`` library.
All caldav-specific exceptions are converted to typed
:class:`CalendarError` subclasses.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from ._shared import (
    CalendarEvent,
    Contact,
    Task,
    _wrap_caldav_op,
)
from .calendar_ops import _CalendarOpsMixin
from .contact_ops import _ContactOpsMixin
from .exceptions import (
    AgentLogicError,
    AuthError,
    CalDAVError,
    CalendarError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)
from .task_ops import _TaskOpsMixin

logger = logging.getLogger(__name__)

__all__ = [
    "AgentLogicError",
    "AuthError",
    "CalDAVError",
    "CalDavClient",
    "CalendarError",
    "CalendarEvent",
    "ConflictError",
    "Contact",
    "NotFoundError",
    "RateLimitError",
    "Task",
]


class CalDavClient(_CalendarOpsMixin, _ContactOpsMixin, _TaskOpsMixin):
    """Typed wrapper around ``caldav.DAVClient`` for Radicale.

    All operations convert caldav/requests exceptions to typed
    :class:`CalendarError` subclasses.

    Args:
        url: Radicale server URL.
        username: Radicale username.
        password: Radicale password.
        timeout: Timeout in seconds for CalDAV HTTP requests (default 30).

    Raises:
        AuthError: If authentication fails.
        CalDAVError: If connection to Radicale fails.
    """

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        default_calendar: str = "",
        timeout: int = 30,
    ) -> None:
        # ``caldav`` ships incomplete type information (mypy resolves the
        # module to ``object``), so route it through ``Any`` to keep the
        # wrapper strict-clean without per-call ignores.
        import caldav

        self._caldav: Any = caldav

        self._url = url
        self._default_calendar = default_calendar
        try:
            self._client = self._caldav.DAVClient(
                url=url, username=username, password=password, timeout=timeout
            )
            self._principal = self._client.principal()
            logger.info("CalDavClient connected to %s as %s", url, username)
        except self._caldav.error.AuthorizationError as exc:
            logger.exception("CalDAV auth failed for %s as %s: %s", url, username, exc)
            raise AuthError(
                f"Authentication failed: {exc}",
            ) from exc
        except Exception as exc:
            logger.exception("Failed to connect to Radicale at %s: %s", url, exc)
            raise CalDAVError(
                f"Failed to connect to Radicale: {exc}",
            ) from exc

    def _get_calendar(self, calendar_id: str = "") -> Any:
        """Return a caldav calendar object by name, or the default.

        When *calendar_id* is empty, resolve in order:
        1. ``self._default_calendar`` by name (when configured).
        2. The first calendar (``calendars[0]``) as a last-resort fallback.
        """
        calendars = self._principal.calendars()
        if not calendars:
            raise NotFoundError(
                "No calendars found on the server.",
            )
        if calendar_id:
            for cal in calendars:
                if cal.name == calendar_id:
                    return cal
            raise NotFoundError(
                f"Calendar {calendar_id!r} not found.",
            )
        # Resolve the configured default calendar by name.
        if self._default_calendar:
            for cal in calendars:
                if cal.name == self._default_calendar:
                    return cal
            raise NotFoundError(
                f"Default calendar {self._default_calendar!r} not found.",
            )
        # Last-resort fallback: first calendar (preserves legacy behavior).
        return calendars[0]

    def _iter_calendars(self, calendar_id: str = "") -> list[Any]:
        """Return calendars to iterate over.

        When *calendar_id* is non-empty, returns a single-element list
        containing the named calendar.  When empty, returns **all**
        calendars (raising ``not_found`` if none exist).
        """
        if calendar_id:
            return [self._get_calendar(calendar_id)]
        calendars = self._principal.calendars()
        if not calendars:
            raise NotFoundError(
                "No calendars found on the server.",
            )
        return cast(list[Any], calendars)

    def _get_addressbook(self, addressbook_id: str = "") -> Any:
        """Return a caldav addressbook object by name, or the default."""
        addressbooks = self._principal.addressbooks()
        if not addressbooks:
            raise NotFoundError(
                "No address books found on the server.",
            )
        if addressbook_id:
            for ab in addressbooks:
                if ab.name == addressbook_id:
                    return ab
            raise NotFoundError(
                f"Address book {addressbook_id!r} not found.",
            )
        return addressbooks[0]

    @staticmethod
    def _escape_text(value: str) -> str:
        r"""Escape special characters for iCalendar/vCard text values.

        Per RFC 5545 §3.3.11 and RFC 6350 §3.4, the following characters
        must be escaped with a backslash in text property values:
        ``\`` → ``\\``, ``;`` → ``\;``, ``,`` → ``\,``, newline → ``\n``.
        """
        if not value:
            return value
        result = value.replace("\\", "\\\\")
        result = result.replace(";", "\\;")
        result = result.replace(",", "\\,")
        result = result.replace("\n", "\\n")
        return result

    @staticmethod
    def _ical_dt(name: str, value: str) -> str:
        """Format a date/datetime as an RFC 5545 iCalendar property line.

        Accepts ISO-8601 (extended ``2026-06-25T15:00:00`` or basic
        ``20260625T150000``) and emits valid iCalendar basic format:
        ``DTSTART:20260625T150000`` (floating), ``...Z`` (UTC), or
        ``DTSTART;VALUE=DATE:20260625`` (date-only). Radicale rejects the
        extended ISO form (colons/dashes) with ``400 Bad Request``.
        """
        import datetime

        s = (value or "").strip()
        if "T" in s:
            try:
                dt = datetime.datetime.fromisoformat(s)
            except ValueError, TypeError:
                dt = None
            if dt is not None:
                if dt.tzinfo is not None:
                    dt = dt.astimezone(datetime.UTC)
                    return f"{name}:{dt.strftime('%Y%m%dT%H%M%SZ')}"
                return f"{name}:{dt.strftime('%Y%m%dT%H%M%S')}"
        else:
            try:
                d = datetime.date.fromisoformat(s)
                return f"{name};VALUE=DATE:{d.strftime('%Y%m%d')}"
            except ValueError, TypeError:
                pass
        # Unparseable — pass through (server will reject if truly invalid).
        return f"{name}:{s}"

    # ------------------------------------------------------------------
    # misc operations
    # ------------------------------------------------------------------

    @_wrap_caldav_op("list calendars")
    def list_calendars(self) -> list[str]:
        """Return the names of all available calendar collections.

        Only VEVENT / calendar collections are included (addressbooks
        come from the separate ``self._principal.addressbooks()`` and
        are inherently excluded).
        """
        return [cal.name for cal in self._principal.calendars()]

    # ------------------------------------------------------------------
    # Health probe
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Perform a one-shot CalDAV reachability check.

        Returns:
            ``{"connected": True, "calendar_count": int}`` on success, or
            ``{"connected": False, "error": str}`` when the probe fails.

        Can be called on demand (e.g. via a health-check endpoint) — it
        does **not** cache stale state.
        """
        try:
            calendars = self._principal.calendars()
        except Exception as exc:
            logger.warning("CalDAV health probe failed: %s", exc)
            return {"connected": False, "error": str(exc)}
        else:
            return {"connected": True, "calendar_count": len(calendars)}
