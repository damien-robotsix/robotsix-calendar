"""Calendar event CRUD operations for CalDavClient (mixin)."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from ._shared import (
    CalendarEvent,
    _comp_dt,
    _comp_text,
    _wrap_caldav_op,
)
from .exceptions import NotFoundError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ._shared import _CalDavClientProtocol

    _MixinBase = _CalDavClientProtocol
else:
    _MixinBase = object


class _CalendarOpsMixin(_MixinBase):
    """Mixin providing calendar event CRUD methods.

    Mixed into :class:`CalDavClient` alongside the other domain mixins.
    The host-class contract (``_escape_text``, ``_ical_dt``,
    ``_iter_calendars``, ``_get_calendar``, ...) is supplied under
    ``TYPE_CHECKING`` by :class:`_CalDavClientProtocol` rather than
    re-declared here.
    """

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _iso_date_range(start: str, end: str) -> tuple[Any, Any]:
        """Parse ISO 8601 strings into date/datetime objects for caldav."""
        import datetime

        def _parse(s: str) -> Any:
            s = s.strip()
            try:
                return datetime.datetime.fromisoformat(s)
            except ValueError, TypeError:
                pass
            try:
                return datetime.date.fromisoformat(s)
            except ValueError, TypeError:
                return s

        return _parse(start), _parse(end)

    @staticmethod
    def _to_calendar_event(obj: Any, calendar_id: str = "") -> CalendarEvent:
        """Convert a caldav event object to our :class:`CalendarEvent`.

        Reads via caldav 2.0's ``icalendar_component`` (the ``icalendar`` lib),
        replacing the deprecated ``vobject_instance``.
        """
        comp = obj.icalendar_component

        return CalendarEvent(
            uid=_comp_text(comp, "UID"),
            summary=_comp_text(comp, "SUMMARY"),
            description=_comp_text(comp, "DESCRIPTION"),
            location=_comp_text(comp, "LOCATION"),
            dtstart=_comp_dt(comp, "DTSTART"),
            dtend=_comp_dt(comp, "DTEND"),
            calendar_id=calendar_id,
        )

    def _event_to_ical(self, event: CalendarEvent) -> str:
        """Build an iCalendar string from a :class:`CalendarEvent`."""
        import datetime

        e = self._escape_text
        dtstamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        return (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "PRODID:-//robotsix-calendar-agent//EN\n"
            "BEGIN:VEVENT\n"
            f"UID:{event.uid or ''}\n"
            f"DTSTAMP:{dtstamp}\n"
            f"SUMMARY:{e(event.summary)}\n"
            f"DESCRIPTION:{e(event.description)}\n"
            f"LOCATION:{e(event.location)}\n"
            f"{self._ical_dt('DTSTART', event.dtstart)}\n"
            f"{self._ical_dt('DTEND', event.dtend)}\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )

    def _find_event_by_uid(self, uid: str) -> tuple[Any, Any] | None:
        """Locate an event by UID across all calendars.

        Returns ``(calendar, event_obj)`` or ``None`` if not found.
        """
        for cal in self._iter_calendars(""):
            event_obj = cal.event(uid=uid)
            if event_obj is not None:
                return cal, event_obj
        return None

    # ------------------------------------------------------------------
    # Calendar CRUD
    # ------------------------------------------------------------------

    @_wrap_caldav_op("list events")
    def list_events(
        self, start: str, end: str, calendar_id: str = ""
    ) -> list[CalendarEvent]:
        """Return events in the ISO 8601 date range.

        When *calendar_id* is empty, events are aggregated from **all**
        calendars.  Each event is tagged with its source ``calendar_id``.
        """
        logger.debug(
            "list_events start=%r end=%r calendar_id=%r",
            start,
            end,
            calendar_id,
        )
        start_dt, end_dt = self._iso_date_range(start, end)
        aggregated: list[CalendarEvent] = []
        for cal in self._iter_calendars(calendar_id):
            results = cal.search(
                start=start_dt,
                end=end_dt,
                event=True,
                expand=False,
            )
            aggregated.extend(
                self._to_calendar_event(r, calendar_id=cal.name) for r in results
            )
        return aggregated

    @_wrap_caldav_op("create event")
    def create_event(
        self, event: CalendarEvent, calendar_id: str = ""
    ) -> CalendarEvent:
        """Create an event; return the event with its server-assigned uid.

        If *calendar_id* is empty, use the default calendar.
        """
        logger.debug(
            "create_event uid=%r calendar_id=%r summary=%r",
            event.uid,
            calendar_id,
            event.summary,
        )
        if not event.uid:
            # Generate a temporary UID; the server may replace it.
            event = CalendarEvent(
                uid=str(uuid.uuid4()),
                summary=event.summary,
                description=event.description,
                location=event.location,
                dtstart=event.dtstart,
                dtend=event.dtend,
                calendar_id=event.calendar_id,
            )
        cal = self._get_calendar(calendar_id)
        ical = self._event_to_ical(event)
        saved = cal.save_event(ical)
        return self._to_calendar_event(saved, calendar_id=cal.name)

    @_wrap_caldav_op("update event")
    def update_event(
        self, uid: str, event: CalendarEvent, calendar_id: str = ""
    ) -> CalendarEvent:
        """Update the event identified by *uid*; return the updated event.

        When *calendar_id* is empty, iterates **all** calendars to locate
        the UID (the UID may live in a non-default collection).  When
        *calendar_id* is given, only that single calendar is searched.

        Raises:
            NotFoundError: If the UID doesn't exist.
        """
        logger.debug(
            "update_event uid=%r calendar_id=%r summary=%r",
            uid,
            calendar_id,
            event.summary,
        )
        if calendar_id:
            cal = self._get_calendar(calendar_id)
            existing = cal.event(uid=uid)
            if existing is None:
                raise NotFoundError(
                    f"Event with UID {uid!r} not found.",
                )
        else:
            result = self._find_event_by_uid(uid)
            if result is None:
                raise NotFoundError(
                    f"Event with UID {uid!r} not found.",
                )
            cal, _ = result
        # Build updated iCal with the same UID
        updated = CalendarEvent(
            uid=uid,
            summary=event.summary,
            description=event.description,
            location=event.location,
            dtstart=event.dtstart,
            dtend=event.dtend,
            calendar_id=calendar_id or cal.name,
        )
        ical = self._event_to_ical(updated)
        saved = cal.save_event(ical)
        return self._to_calendar_event(saved, calendar_id=cal.name)

    @_wrap_caldav_op("delete event")
    def delete_event(self, uid: str, calendar_id: str = "") -> None:
        """Delete the event identified by *uid*. Idempotent.

        When *calendar_id* is empty, iterates **all** calendars to locate
        the UID.  Returns ``None`` when the UID does not exist in any
        calendar (already deleted).
        """
        logger.debug("delete_event uid=%r calendar_id=%r", uid, calendar_id)
        if calendar_id:
            cal = self._get_calendar(calendar_id)
            event_obj = cal.event(uid=uid)
            if event_obj is None:
                return None
            event_obj.delete()
        else:
            result = self._find_event_by_uid(uid)
            if result is None:
                return None
            _cal, event_obj = result
            event_obj.delete()
            return None
