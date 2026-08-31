"""Tests for calendar operations — CRUD, resolution, serialization."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from robotsix_calendar.caldav_client import (
    CalDavClient,
    CalendarEvent,
)
from robotsix_calendar.caldav_client.exceptions import (
    NotFoundError,
)
from tests.caldav_client.conftest import _make_event, _mock_vevent

# ---------------------------------------------------------------------------
# Calendar CRUD
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_returns_list_of_calendar_events(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.search.return_value = [_mock_vevent(), _mock_vevent(uid="evt-2")]

        result = client.list_events("2026-06-01", "2026-06-30")

        assert len(result) == 2
        assert isinstance(result[0], CalendarEvent)
        assert result[0].uid == "evt-1"
        assert result[1].uid == "evt-2"


class TestCreateEvent:
    def test_returns_event_with_uid(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.return_value = _mock_vevent(uid="new-uid")

        event = _make_event()
        result = client.create_event(event)

        assert isinstance(result, CalendarEvent)
        assert result.uid == "new-uid"
        cal.save_event.assert_called_once()


class TestUpdateEvent:
    def test_returns_updated_event(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.return_value = _mock_vevent(uid="evt-1")
        cal.save_event.return_value = _mock_vevent(uid="evt-1", summary="Updated")

        event = _make_event(summary="Updated")
        result = client.update_event("evt-1", event)

        assert result.summary == "Updated"

    def test_raises_not_found_for_unknown_uid(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.return_value = None

        with pytest.raises(NotFoundError, match="not found"):
            client.update_event("unknown", _make_event())


class TestDeleteEvent:
    def test_succeeds(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        mock_event = MagicMock()
        cal.event.return_value = mock_event

        client.delete_event("evt-1")  # should not raise

        mock_event.delete.assert_called_once()

    def test_returns_none_for_unknown_uid(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.return_value = None

        result = client.delete_event("unknown")
        assert result is None


# ---------------------------------------------------------------------------
# Calendar / addressbook resolution
# ---------------------------------------------------------------------------


class TestGetCalendar:
    def test_no_calendars_raises_not_found(self, client: CalDavClient) -> None:
        client._principal.calendars.return_value = []

        with pytest.raises(NotFoundError) as exc_info:
            client._get_calendar()
        assert exc_info.value.code == "not_found"

    def test_named_calendar_returned(self, client: CalDavClient) -> None:
        cal_a = MagicMock()
        cal_a.name = "work"
        cal_b = MagicMock()
        cal_b.name = "home"
        client._principal.calendars.return_value = [cal_a, cal_b]

        assert client._get_calendar("home") is cal_b

    def test_named_calendar_not_found_raises(self, client: CalDavClient) -> None:
        cal_a = MagicMock()
        cal_a.name = "work"
        client._principal.calendars.return_value = [cal_a]

        with pytest.raises(NotFoundError) as exc_info:
            client._get_calendar("missing")
        assert exc_info.value.code == "not_found"

    def test_resolves_configured_default_by_name(self) -> None:
        client = CalDavClient("https://x.com", "u", "p", default_calendar="Birthdays")
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        client._principal.calendars.return_value = [cal_a, cal_b]

        assert client._get_calendar("") is cal_b

    def test_default_not_found_raises(self) -> None:
        client = CalDavClient("https://x.com", "u", "p", default_calendar="Missing")
        cal = MagicMock(name="Robotsix")
        cal.name = "Robotsix"
        client._principal.calendars.return_value = [cal]

        with pytest.raises(NotFoundError, match="not found"):
            client._get_calendar("")

    def test_falls_back_to_first_when_no_default(self) -> None:
        client = CalDavClient("https://x.com", "u", "p")  # no default
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        client._principal.calendars.return_value = [cal_a, cal_b]

        assert client._get_calendar("") is cal_a


class TestIterCalendars:
    def test_returns_all_when_empty_id(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client._iter_calendars("")
        assert result == [cal_a, cal_b]

    def test_returns_single_when_id_given(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client._iter_calendars("Birthdays")
        assert result == [cal_b]

    def test_raises_when_no_calendars(self, client: CalDavClient) -> None:
        client._principal.calendars.return_value = []

        with pytest.raises(NotFoundError) as exc_info:
            client._iter_calendars("")
        assert exc_info.value.code == "not_found"


class TestListCalendars:
    def test_returns_calendar_names(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        cal_c = MagicMock(name="Damien")
        cal_c.name = "Damien"
        client._principal.calendars.return_value = [cal_a, cal_b, cal_c]

        result = client.list_calendars()
        assert result == ["Robotsix", "Birthdays", "Damien"]

    def test_excludes_addressbooks(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        ab = MagicMock(name="contacts-addressbook")
        ab.name = "contacts-addressbook"
        client._principal.calendars.return_value = [cal_a]
        client._principal.addressbooks.return_value = [ab]

        result = client.list_calendars()
        assert result == ["Robotsix"]


class TestListEventsAggregation:
    def test_aggregates_across_all_calendars_when_calendar_id_empty(
        self, client: CalDavClient
    ) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.search.return_value = [_mock_vevent(uid="evt-a", summary="Event A")]
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        cal_b.search.return_value = [_mock_vevent(uid="evt-b", summary="Event B")]
        cal_c = MagicMock(name="Damien")
        cal_c.name = "Damien"
        cal_c.search.return_value = [
            _mock_vevent(uid="evt-c", summary="Event C"),
            _mock_vevent(uid="evt-c2", summary="Event C2"),
        ]
        client._principal.calendars.return_value = [cal_a, cal_b, cal_c]

        result = client.list_events("2026-01-01", "2026-01-31")

        assert len(result) == 4
        assert result[0].uid == "evt-a"
        assert result[0].calendar_id == "Robotsix"
        assert result[1].uid == "evt-b"
        assert result[1].calendar_id == "Birthdays"
        assert result[2].uid == "evt-c"
        assert result[2].calendar_id == "Damien"
        assert result[3].uid == "evt-c2"
        assert result[3].calendar_id == "Damien"

    def test_single_calendar_when_id_provided(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.search.return_value = [_mock_vevent(uid="evt-a")]
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client.list_events("2026-01-01", "2026-01-31", calendar_id="Robotsix")

        assert len(result) == 1
        assert result[0].uid == "evt-a"
        cal_b.search.assert_not_called()


class TestCreateEventDefault:
    def test_writes_to_configured_default(self) -> None:
        client = CalDavClient("https://x.com", "u", "p", default_calendar="Birthdays")
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        cal_b.save_event.return_value = _mock_vevent(uid="new-evt")
        client._principal.calendars.return_value = [cal_a, cal_b]

        event = _make_event()
        result = client.create_event(event)

        cal_b.save_event.assert_called_once()
        assert result.calendar_id == "Birthdays"

    def test_explicit_calendar_id_overrides_default(self) -> None:
        client = CalDavClient("https://x.com", "u", "p", default_calendar="Birthdays")
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.save_event.return_value = _mock_vevent(uid="new-evt")
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        client._principal.calendars.return_value = [cal_a, cal_b]

        event = _make_event()
        result = client.create_event(event, calendar_id="Robotsix")

        cal_a.save_event.assert_called_once()
        assert result.calendar_id == "Robotsix"


# ---------------------------------------------------------------------------
# Conversion / serialization helpers
# ---------------------------------------------------------------------------


class TestIsoDateRange:
    def test_unparseable_returned_as_string(self) -> None:
        start, end = CalDavClient._iso_date_range("not-a-date", "also-bad")
        assert start == "not-a-date"
        assert end == "also-bad"

    def test_date_only_format(self) -> None:
        import datetime

        start, _ = CalDavClient._iso_date_range("2026-06-15", "2026-06-16")
        assert isinstance(start, datetime.datetime)

    def test_datetime_with_utc_z_suffix(self) -> None:
        import datetime

        start, end = CalDavClient._iso_date_range(
            "2026-03-01T10:00:00Z", "2026-03-01T11:00:00Z"
        )
        assert isinstance(start, datetime.datetime)
        assert isinstance(end, datetime.datetime)
        assert start.tzinfo is not None
        assert end.tzinfo is not None

    def test_datetime_with_timezone_offset(self) -> None:
        import datetime

        start, end = CalDavClient._iso_date_range(
            "2026-01-15T14:30:00+01:00", "2026-01-15T15:30:00+01:00"
        )
        assert isinstance(start, datetime.datetime)
        assert isinstance(end, datetime.datetime)
        assert start.tzinfo is not None
        assert end.tzinfo is not None


class TestToCalendarEvent:
    def test_formats_datetime_and_date_values(self) -> None:
        import datetime

        obj = _mock_vevent(
            uid="evt-x",
            summary="Sum",
            description="Desc",
            location="Loc",
            dtstart=datetime.datetime(2026, 6, 15, 9, 0, 0),
            dtend=datetime.date(2026, 6, 15),
        )

        event = CalDavClient._to_calendar_event(obj, calendar_id="cal")

        assert event.uid == "evt-x"
        assert event.dtstart == "2026-06-15T09:00:00"
        assert event.dtend == "2026-06-15"
        assert event.calendar_id == "cal"

    def test_missing_fields_yield_empty(self) -> None:
        comp = MagicMock()
        comp.get.side_effect = lambda _name, default=None: default
        obj = MagicMock()
        obj.icalendar_component = comp

        event = CalDavClient._to_calendar_event(obj)

        assert event.uid == ""
        assert event.summary == ""
        assert event.dtstart == ""
        assert event.dtend == ""


class TestIcalSerialization:
    def test_basic_event(self, client: CalDavClient) -> None:
        event = CalendarEvent(
            uid="evt-1",
            summary="Team Meeting",
            description="Discuss Q3 goals",
            location="Room 101",
            dtstart="20260101T090000Z",
            dtend="20260101T100000Z",
        )
        ical = client._event_to_ical(event)
        assert "SUMMARY:Team Meeting" in ical
        assert "DESCRIPTION:Discuss Q3 goals" in ical
        assert "LOCATION:Room 101" in ical

    def test_iso_extended_dates_converted_to_ical_basic(
        self, client: CalDavClient
    ) -> None:
        # auto-mail / the LLM produce ISO-extended datetimes; Radicale rejects
        # the extended form (colons/dashes) with 400 — they must be normalised.
        event = CalendarEvent(
            uid="evt-iso",
            summary="ISO",
            dtstart="2026-06-25T15:00:00",
            dtend="2026-06-25T16:00:00",
        )
        ical = client._event_to_ical(event)
        assert "DTSTART:20260625T150000" in ical
        assert "DTEND:20260625T160000" in ical
        assert "DTSTART:2026-06-25T15:00:00" not in ical
        assert "DTSTAMP:" in ical

    def test_basic_and_utc_dates_preserved(self, client: CalDavClient) -> None:
        event = CalendarEvent(
            uid="evt-utc",
            summary="UTC",
            dtstart="20260101T090000Z",
            dtend="20260101T100000Z",
        )
        ical = client._event_to_ical(event)
        assert "DTSTART:20260101T090000Z" in ical
        assert "DTEND:20260101T100000Z" in ical

    def test_date_only_uses_value_date(self, client: CalDavClient) -> None:
        event = CalendarEvent(
            uid="evt-day",
            summary="All day",
            dtstart="2026-06-25",
            dtend="2026-06-26",
        )
        ical = client._event_to_ical(event)
        assert "DTSTART;VALUE=DATE:20260625" in ical
        assert "DTEND;VALUE=DATE:20260626" in ical

    def test_escapes_special_characters(self, client: CalDavClient) -> None:
        event = CalendarEvent(
            summary="a\\b;c,d\ne",
            description="desc\\with;special,chars\nhere",
            location="Room; A, B\\C\nDownstairs",
            dtstart="20260101T090000Z",
            dtend="20260101T100000Z",
        )
        ical = client._event_to_ical(event)
        assert "SUMMARY:a\\\\b\\;c\\,d\\ne" in ical
        assert "DESCRIPTION:desc\\\\with\\;special\\,chars\\nhere" in ical
        assert "LOCATION:Room\\; A\\, B\\\\C\\nDownstairs" in ical
