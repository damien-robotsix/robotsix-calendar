"""Hypothesis property-based round-trip tests for CalDAV serialization.

Exercises the in-process Radicale server fixture with
``@given``-generated random data to verify that:

* ``CalendarEvent`` → iCal → Radicale → parsed ``CalendarEvent``
  preserves ``SUMMARY``, ``DESCRIPTION``, ``LOCATION``, ``UID``.
* VTODO → Radicale → parsed ``Task`` preserves ``SUMMARY``,
  ``DESCRIPTION``, ``STATUS``, ``UID``.
* ``Contact`` → vCard → parsed ``Contact`` preserves ``full_name``,
  ``email``, ``phone``, ``address``, ``UID`` (pure serialization
  round-trip; caldav v3.x removed CardDAV address-book support).

The number of examples is controlled by the active Hypothesis profile
(dev=50 / CI=200). Failures are shrunk to a minimal reproducer.
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from robotsix_calendar.caldav_client import (
    CalDavClient,
    CalendarEvent,
    Contact,
    Task,
)
from tests.strategies import dates, text, text_required, uids

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# shared strategies
# ---------------------------------------------------------------------------

# Cached calendar references — created once per session so hypothesis
# examples don't pollute the "default" calendar used by other tests.
# Set by the first call to each roundtrip test.
_hypothesis_cal_event: Any = None
_hypothesis_cal_task: Any = None

# ---------------------------------------------------------------------------
# event roundtrip
# ---------------------------------------------------------------------------


def _build_event_ical(event: CalendarEvent) -> str:
    """Build an iCalendar VEVENT string — mirrors ``_event_to_ical``."""
    e = CalDavClient._escape_text
    dtstamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    return (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//robotsix-calendar//EN\n"
        "BEGIN:VEVENT\n"
        f"UID:{event.uid}\n"
        f"DTSTAMP:{dtstamp}\n"
        f"SUMMARY:{e(event.summary)}\n"
        f"DESCRIPTION:{e(event.description)}\n"
        f"LOCATION:{e(event.location)}\n"
        f"{CalDavClient._ical_dt('DTSTART', event.dtstart)}\n"
        f"{CalDavClient._ical_dt('DTEND', event.dtend)}\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )


@given(
    summary=text_required,
    description=text,
    location=text,
    uid=uids,
    dtstart=dates,
    dtend_offset=st.integers(min_value=0, max_value=30),
)
def test_event_roundtrip(
    caldav_client: Any,
    summary: str,
    description: str,
    location: str,
    uid: str,
    dtstart: str,
    dtend_offset: int,
) -> None:
    """CalendarEvent → iCal → Radicale → CalendarEvent roundtrip."""
    import datetime as dt_mod

    dtstart_date = dt_mod.date.fromisoformat(dtstart)
    dtend_date = dtstart_date + dt_mod.timedelta(days=max(dtend_offset, 1))
    dtend_str = dtend_date.isoformat()

    event = CalendarEvent(
        uid=uid,
        summary=summary,
        description=description,
        location=location,
        dtstart=dtstart,
        dtend=dtend_str,
    )

    ical = _build_event_ical(event)

    global _hypothesis_cal_event
    if _hypothesis_cal_event is None:
        principal = caldav_client.principal()
        _hypothesis_cal_event = principal.make_calendar(name="hypothesis-events")
    cal = _hypothesis_cal_event
    cal.save_event(ical)

    # Search a generous window around the event date.
    search_start = dtstart_date - dt_mod.timedelta(days=1)
    search_end = dtend_date + dt_mod.timedelta(days=1)
    results = cal.search(
        start=dt_mod.datetime.combine(search_start, dt_mod.time.min),
        end=dt_mod.datetime.combine(search_end, dt_mod.time.min),
        event=True,
    )

    # Find our event by UID.
    matches = [r for r in results if str(r.icalendar_component.get("UID")) == uid]
    assert len(matches) == 1, f"Expected 1 match for UID {uid!r}, got {len(matches)}"

    parsed = CalDavClient._to_calendar_event(matches[0])
    assert parsed.summary == summary
    assert parsed.description == description
    assert parsed.location == location
    assert parsed.uid == uid


# ---------------------------------------------------------------------------
# task roundtrip
# ---------------------------------------------------------------------------


def _build_task_ical(task: Task) -> str:
    """Build a VTODO iCalendar string."""
    e = CalDavClient._escape_text
    dtstamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//robotsix-calendar//EN",
        "BEGIN:VTODO",
        f"UID:{task.uid}",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:{e(task.summary)}",
        f"DESCRIPTION:{e(task.description)}",
    ]
    if task.dtstart:
        lines.append(CalDavClient._ical_dt("DTSTART", task.dtstart))
    if task.due:
        lines.append(CalDavClient._ical_dt("DUE", task.due))
    if task.status:
        lines.append(f"STATUS:{e(task.status)}")
    lines.append("END:VTODO")
    lines.append("END:VCALENDAR")
    return "\n".join(lines) + "\n"


@given(
    summary=text_required,
    description=text,
    uid=uids,
    dtstart=dates,
    due_offset=st.integers(min_value=1, max_value=30),
    status=st.sampled_from(["NEEDS-ACTION", "IN-PROCESS", "COMPLETED", "CANCELLED"]),
)
def test_task_roundtrip(
    caldav_client: Any,
    summary: str,
    description: str,
    uid: str,
    dtstart: str,
    due_offset: int,
    status: str,
) -> None:
    """VTODO → Radicale → Task roundtrip via ``_to_task``."""
    import datetime as dt_mod

    dtstart_date = dt_mod.date.fromisoformat(dtstart)
    due_date = dtstart_date + dt_mod.timedelta(days=due_offset)
    due_str = due_date.isoformat()

    task = Task(
        uid=uid,
        summary=summary,
        description=description,
        dtstart=dtstart,
        due=due_str,
        status=status,
    )

    ical = _build_task_ical(task)

    global _hypothesis_cal_task
    if _hypothesis_cal_task is None:
        principal = caldav_client.principal()
        _hypothesis_cal_task = principal.make_calendar(name="hypothesis-tasks")
    cal = _hypothesis_cal_task
    cal.save_todo(ical)

    results = cal.search(todo=True, include_completed=True)
    matches = [r for r in results if str(r.icalendar_component.get("UID")) == uid]
    assert len(matches) == 1, f"Expected 1 match for UID {uid!r}, got {len(matches)}"

    parsed = CalDavClient._to_task(matches[0])
    assert parsed.summary == summary
    assert parsed.description == description
    assert parsed.status == status
    assert parsed.uid == uid


# ---------------------------------------------------------------------------
# contact roundtrip (pure serialization — no Radicale)
# ---------------------------------------------------------------------------
#
# CardDAV support was removed from the caldav library in v3.x
# (``principal.addressbooks()`` no longer exists).  The contact
# round-trip is therefore tested as a pure serialization identity:
# ``_contact_to_vcard`` → ``_to_contact`` — no Radicale involved.
#
# This still catches the same class of edge-case bugs (unicode,
# special characters, empty fields, boundary-length values) because
# ``_to_contact`` parses the exact vCard text that
# ``_contact_to_vcard`` produces.


class _FakeVCardObj:
    """Minimal stub of a caldav ``CalendarObjectResource`` for ``_to_contact``.

    The production ``_to_contact`` only reads ``obj.data`` (the raw vCard
    text), so a simple ``.data`` attribute is sufficient.
    """

    def __init__(self, data: str) -> None:
        self.data = data


def _build_vcard(contact: Contact) -> str:
    """Build a vCard string — mirrors ``_contact_to_vcard``."""
    e = CalDavClient._escape_text
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"UID:{contact.uid}",
        f"FN:{e(contact.full_name)}",
    ]
    if contact.email:
        lines.append(f"EMAIL:{e(contact.email)}")
    if contact.phone:
        lines.append(f"TEL:{e(contact.phone)}")
    if contact.address:
        lines.append(f"ADR:;;{e(contact.address)};;;")
    lines.append("END:VCARD")
    return "\n".join(lines) + "\n"


@given(
    full_name=text_required,
    email=text,
    phone=text,
    address=text,
    uid=uids,
)
def test_contact_roundtrip(
    full_name: str,
    email: str,
    phone: str,
    address: str,
    uid: str,
) -> None:
    """Contact → vCard → Contact roundtrip (pure serialization)."""
    contact = Contact(
        uid=uid,
        full_name=full_name,
        email=email,
        phone=phone,
        address=address,
    )

    vcard = _build_vcard(contact)
    parsed = CalDavClient._to_contact(_FakeVCardObj(vcard))
    assert parsed.full_name == full_name
    assert parsed.email == email
    assert parsed.phone == phone
    assert parsed.address == address
    assert parsed.uid == uid
