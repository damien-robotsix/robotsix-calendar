"""Task (VTODO) operations for CalDavClient (mixin)."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from ._shared import Task, _comp_dt, _comp_text, _wrap_caldav_op
from .exceptions import NotFoundError

logger = logging.getLogger(__name__)


class _TaskOpsMixin:
    """Mixin providing VTODO task operations.

    Mixed into :class:`CalDavClient` alongside the other domain mixins.
    """

    if TYPE_CHECKING:
        # Provided by CalDavClient at runtime; declared here so mypy
        # understands the mixin contract without circular imports.
        def _escape_text(self, value: str) -> str:
            raise NotImplementedError

        def _ical_dt(self, name: str, value: str) -> str:
            raise NotImplementedError

        def _iter_calendars(self, calendar_id: str = "") -> list[Any]:
            raise NotImplementedError

        def _get_calendar(self, calendar_id: str = "") -> Any:
            raise NotImplementedError

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_task(obj: Any, calendar_id: str = "") -> Task:
        """Convert a caldav VTODO object to our :class:`Task`.

        Reads via caldav 2.0's ``icalendar_component`` (the ``icalendar`` lib),
        same pattern as ``_to_calendar_event`` but for VTODO fields.
        """
        comp = obj.icalendar_component

        return Task(
            uid=_comp_text(comp, "UID"),
            summary=_comp_text(comp, "SUMMARY"),
            description=_comp_text(comp, "DESCRIPTION"),
            dtstart=_comp_dt(comp, "DTSTART"),
            due=_comp_dt(comp, "DUE"),
            status=_comp_text(comp, "STATUS"),
            calendar_id=calendar_id,
        )

    def _task_to_ical(self, task: Task) -> str:
        """Build an iCalendar string from a :class:`Task`."""
        import datetime

        e = self._escape_text
        dtstamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        return (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "PRODID:-//robotsix-calendar-agent//EN\n"
            "BEGIN:VTODO\n"
            f"UID:{task.uid or ''}\n"
            f"DTSTAMP:{dtstamp}\n"
            f"SUMMARY:{e(task.summary)}\n"
            f"DESCRIPTION:{e(task.description)}\n"
            f"{self._ical_dt('DTSTART', task.dtstart)}\n"
            f"{self._ical_dt('DUE', task.due)}\n"
            f"STATUS:{task.status or 'NEEDS-ACTION'}\n"
            "END:VTODO\n"
            "END:VCALENDAR\n"
        )

    def _find_task_by_uid(self, uid: str) -> tuple[Any, Any] | None:
        """Locate a task by UID across all calendars.

        Returns ``(calendar, task_obj)`` or ``None`` if not found.
        """
        for cal in self._iter_calendars(""):
            results = cal.search(todo=True)
            for obj in results:
                comp = obj.icalendar_component
                if _comp_text(comp, "UID") == uid:
                    return cal, obj
        return None

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    @_wrap_caldav_op("list tasks")
    def list_tasks(self, calendar_id: str = "") -> list[Task]:
        """Return all VTODO tasks from CalDAV calendar collections.

        When *calendar_id* is empty, tasks are aggregated from **all**
        calendars.  Each task is tagged with its source ``calendar_id``.
        """
        logger.debug("list_tasks calendar_id=%r", calendar_id)
        aggregated: list[Task] = []
        for cal in self._iter_calendars(calendar_id):
            results = cal.search(todo=True)
            aggregated.extend(self._to_task(r, calendar_id=cal.name) for r in results)
        return aggregated

    @_wrap_caldav_op("create task")
    def create_task(self, task: Task, calendar_id: str = "") -> Task:
        """Create a VTODO task; return the task with its server-assigned uid.

        If *calendar_id* is empty, use the default calendar.
        """
        logger.debug(
            "create_task uid=%r calendar_id=%r summary=%r",
            task.uid,
            calendar_id,
            task.summary,
        )
        if not task.uid:
            task = Task(
                uid=str(uuid.uuid4()),
                summary=task.summary,
                description=task.description,
                dtstart=task.dtstart,
                due=task.due,
                status=task.status,
                calendar_id=task.calendar_id,
            )
        cal = self._get_calendar(calendar_id)
        ical = self._task_to_ical(task)
        saved = cal.save_event(ical)
        return self._to_task(saved, calendar_id=cal.name)

    @_wrap_caldav_op("update task")
    def update_task(self, uid: str, task: Task, calendar_id: str = "") -> Task:
        """Update the task identified by *uid*; return the updated task.

        When *calendar_id* is empty, iterates **all** calendars to locate
        the UID (the UID may live in a non-default collection).  When
        *calendar_id* is given, only that single calendar is searched.

        Raises:
            NotFoundError: If the UID doesn't exist.
        """
        logger.debug(
            "update_task uid=%r calendar_id=%r summary=%r",
            uid,
            calendar_id,
            task.summary,
        )
        if calendar_id:
            cal = self._get_calendar(calendar_id)
            results = cal.search(todo=True)
            existing = None
            for obj in results:
                comp = obj.icalendar_component
                if _comp_text(comp, "UID") == uid:
                    existing = obj
                    break
            if existing is None:
                raise NotFoundError(
                    f"Task with UID {uid!r} not found.",
                )
        else:
            result = self._find_task_by_uid(uid)
            if result is None:
                raise NotFoundError(
                    f"Task with UID {uid!r} not found.",
                )
            cal, _ = result
        # Build updated iCal with the same UID
        updated = Task(
            uid=uid,
            summary=task.summary,
            description=task.description,
            dtstart=task.dtstart,
            due=task.due,
            status=task.status,
            calendar_id=calendar_id or cal.name,
        )
        ical = self._task_to_ical(updated)
        saved = cal.save_event(ical)
        return self._to_task(saved, calendar_id=cal.name)

    @_wrap_caldav_op("delete task")
    def delete_task(self, uid: str, calendar_id: str = "") -> None:
        """Delete the task identified by *uid*. Idempotent.

        When *calendar_id* is empty, iterates **all** calendars to locate
        the UID.  Returns ``None`` when the UID does not exist in any
        calendar (already deleted).
        """
        logger.debug("delete_task uid=%r calendar_id=%r", uid, calendar_id)
        if calendar_id:
            cal = self._get_calendar(calendar_id)
            results = cal.search(todo=True)
            for obj in results:
                comp = obj.icalendar_component
                if _comp_text(comp, "UID") == uid:
                    obj.delete()
                    return None
            return None
        else:
            result = self._find_task_by_uid(uid)
            if result is None:
                return None
            _cal, obj = result
            obj.delete()
            return None
