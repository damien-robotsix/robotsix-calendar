"""Integration tests against a live in-process Radicale server.

These tests use the session-scoped ``caldav_client`` fixture from
``tests/caldav_test_server.py`` to exercise real CalDAV protocol
interactions: PROPFIND, REPORT, MKCALENDAR, PUT, DELETE, and iCal
parsing.

Marked ``integration`` so they can be skipped in quick dev loops
with ``pytest -m "not integration"``.
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Create + search
# ---------------------------------------------------------------------------


def test_create_event_then_search_by_date(caldav_client: Any) -> None:
    """Save an event and retrieve it via date-range search."""
    principal = caldav_client.principal()
    calendars = principal.calendars()
    cal = calendars[0]

    cal.save_event(
        """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-search-1
DTSTART:20260801T090000
DTEND:20260801T100000
SUMMARY:Integration Test Meeting
END:VEVENT
END:VCALENDAR"""
    )

    results = cal.search(
        start=datetime.datetime(2026, 8, 1),
        end=datetime.datetime(2026, 8, 2),
        event=True,
    )

    assert len(results) == 1
    comp = results[0].icalendar_component
    assert str(comp.get("SUMMARY")) == "Integration Test Meeting"
    assert str(comp.get("UID")) == "test-search-1"


# ---------------------------------------------------------------------------
# Recurring-event occurrence expansion
# ---------------------------------------------------------------------------


def test_recurring_event_search_returns_expanded_occurrence(
    caldav_client: Any,
) -> None:
    """A weekly recurrence queried for a later week must return the
    occurrence on that day (``expand=True``), not the master's start.

    Regression for the agenda bug where querying a single day returned a
    recurring event with the master/original ``dtstart`` (the first
    occurrence) instead of the occurrence inside the queried range.
    """
    principal = caldav_client.principal()
    cal = principal.calendars()[0]

    # Weekly recurrence whose master/first occurrence is 2026-10-08.
    cal.save_event(
        """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-weekly-1
DTSTART:20261008T180000
DTEND:20261008T190000
RRULE:FREQ=WEEKLY
SUMMARY:Piano chant et escalade
END:VEVENT
END:VCALENDAR"""
    )

    # Query only 2026-10-15 — one week after the master occurrence.
    results = cal.search(
        start=datetime.datetime(2026, 10, 15, 0, 0, 0),
        end=datetime.datetime(2026, 10, 15, 23, 59, 59),
        event=True,
        expand=True,
    )

    assert len(results) == 1
    comp = results[0].icalendar_component
    assert str(comp.get("SUMMARY")) == "Piano chant et escalade"
    occurrence_start = comp.get("DTSTART").dt
    assert occurrence_start.year == 2026
    assert occurrence_start.month == 10
    assert occurrence_start.day == 15


# ``CalDavClient`` reads ``Calendar.name``, deprecated in real caldav 2.x.
@pytest.mark.filterwarnings("ignore:The 'name' attribute is deprecated")
def test_update_recurring_event_is_rejected_and_series_preserved(
    caldav_client: Any,
) -> None:
    """Updating a recurring event via its (shared) UID must not flatten
    the series into a single event: the update is rejected with
    ``ConflictError`` and the stored RRULE survives.
    """
    from robotsix_calendar.caldav_client import CalDavClient, CalendarEvent
    from robotsix_calendar.caldav_client.exceptions import ConflictError

    principal = caldav_client.principal()
    cal = principal.calendars()[0]
    cal.save_event(
        """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-weekly-update
DTSTART:20261103T100000
DTEND:20261103T103000
RRULE:FREQ=WEEKLY
SUMMARY:Weekly standup
END:VEVENT
END:VCALENDAR"""
    )

    client = CalDavClient(url=str(caldav_client.url), username="x", password="x")

    occurrences = client.list_events("2026-11-01T00:00:00", "2026-11-30T23:59:59")
    standups = [e for e in occurrences if e.uid == "test-weekly-update"]
    assert len(standups) == 4
    assert all(e.recurring for e in standups)

    with pytest.raises(ConflictError, match="recurring"):
        client.update_event(
            "test-weekly-update",
            CalendarEvent(
                summary="Weekly standup",
                dtstart="2026-11-10T11:00:00",
                dtend="2026-11-10T11:30:00",
            ),
        )

    stored = cal.event(uid="test-weekly-update").icalendar_component
    assert stored.get("RRULE") is not None
    assert stored.get("DTSTART").dt == datetime.datetime(2026, 11, 3, 10, 0, 0)


# ---------------------------------------------------------------------------
# Create + delete
# ---------------------------------------------------------------------------


def test_create_event_then_delete(caldav_client: Any) -> None:
    """Save an event, delete it, and verify it is gone."""
    principal = caldav_client.principal()
    calendars = principal.calendars()
    cal = calendars[0]

    cal.save_event(
        """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-delete-1
DTSTART:20260915T140000
DTEND:20260915T150000
SUMMARY:To Be Deleted
END:VEVENT
END:VCALENDAR"""
    )

    # Confirm it exists
    results = cal.search(
        start=datetime.datetime(2026, 9, 15),
        end=datetime.datetime(2026, 9, 16),
        event=True,
    )
    assert len(results) == 1
    assert str(results[0].icalendar_component.get("UID")) == "test-delete-1"

    # Delete it
    results[0].delete()

    # Confirm it is gone
    results = cal.search(
        start=datetime.datetime(2026, 9, 15),
        end=datetime.datetime(2026, 9, 16),
        event=True,
    )
    assert len(results) == 0


# ---------------------------------------------------------------------------
# Malformed iCal error case
# ---------------------------------------------------------------------------


def test_malformed_ical_raises_error(caldav_client: Any) -> None:
    """Sending invalid iCal data should raise an error from the server."""
    from caldav.lib.error import DAVError

    principal = caldav_client.principal()
    calendars = principal.calendars()
    cal = calendars[0]

    # VEVENT without DTSTART — Radicale rejects this with 400.
    missing_dtstart = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-bad-1
SUMMARY:No Start Date
END:VEVENT
END:VCALENDAR"""

    with pytest.raises(DAVError):
        cal.save_event(missing_dtstart)

    # Completely garbled data — Radicale cannot parse this as iCal.
    with pytest.raises(DAVError):
        cal.save_event("NOT A VALID ICALENDAR STRING AT ALL")
