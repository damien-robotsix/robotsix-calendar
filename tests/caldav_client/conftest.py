"""Shared fixtures for caldav_client tests — all caldav calls mocked."""

from __future__ import annotations

import sys
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest

from robotsix_calendar_agent.caldav_client import (
    CalDavClient,
    CalendarEvent,
    Task,
)

# Mock object prepared at module level but NOT yet injected into
# sys.modules.  The reset_mock_caldav fixture (autouse) temporarily
# swaps it in for each test so that session-scoped integration
# fixtures (like caldav_client in tests/caldav_test_server.py) can
# import the real caldav library without interference.
_mock_caldav = MagicMock()
_mock_caldav.error.AuthorizationError = type("AuthorizationError", (Exception,), {})
_mock_caldav.lib.error.NotFoundError = type("NotFoundError", (Exception,), {})
_mock_caldav.lib.error.RateLimitError = type("RateLimitError", (Exception,), {})
_mock_caldav.lib.error.EtagMismatchError = type("EtagMismatchError", (Exception,), {})
# Alias AuthorizationError under lib.error so _wrap_caldav_op's
# self._caldav.lib.error.AuthorizationError resolves.
_mock_caldav.lib.error.AuthorizationError = _mock_caldav.error.AuthorizationError


@pytest.fixture(autouse=True)
def reset_mock_caldav(request: pytest.FixtureRequest) -> Generator[MagicMock]:
    """Replace caldav in sys.modules with mock, reset between tests.

    Saves and restores the real caldav module so that integration
    tests (which use the same session) can import the real library
    outside of mocked test cases.

    Skips itself for tests marked ``integration`` so that
    session-scoped fixtures (like ``caldav_client``) and inline
    ``from caldav.lib.error import DAVError`` resolve against the
    real caldav package.
    """
    if request.node.get_closest_marker("integration"):
        yield _mock_caldav
        return

    original = sys.modules.get("caldav")
    sys.modules["caldav"] = _mock_caldav
    _mock_caldav.reset_mock(return_value=True, side_effect=True)
    # Re-establish default mock structure
    mock_client = MagicMock()
    mock_principal = MagicMock()
    _mock_caldav.DAVClient.return_value = mock_client
    mock_client.principal.return_value = mock_principal

    mock_cal = MagicMock()
    mock_cal.name = "default-cal"
    mock_principal.calendars.return_value = [mock_cal]

    mock_ab = MagicMock()
    mock_ab.name = "default-ab"
    mock_principal.addressbooks.return_value = [mock_ab]

    yield _mock_caldav

    # Restore the real caldav module (or remove if it wasn't there)
    if original is not None:
        sys.modules["caldav"] = original
    else:
        sys.modules.pop("caldav", None)


@pytest.fixture
def client() -> CalDavClient:
    """Return a CalDavClient with a mocked DAV backend."""
    return CalDavClient("https://example.com", "user", "pass")


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------


def _make_event(**overrides: str) -> CalendarEvent:
    defaults: dict[str, str] = {
        "uid": "",
        "summary": "Test Event",
        "description": "desc",
        "location": "room",
        "dtstart": "2026-06-15T09:00:00",
        "dtend": "2026-06-15T10:00:00",
        "calendar_id": "",
    }
    defaults.update(overrides)
    return CalendarEvent(**defaults)


def _make_task(**overrides: str) -> Task:
    defaults: dict[str, str] = {
        "uid": "",
        "summary": "Test Task",
        "description": "task description",
        "dtstart": "2026-06-20T08:00:00",
        "due": "2026-06-21",
        "status": "NEEDS-ACTION",
        "calendar_id": "",
    }
    defaults.update(overrides)
    return Task(**defaults)


def _mock_vevent(**overrides: Any) -> MagicMock:
    """Build a mock caldav object exposing ``icalendar_component`` (caldav 2.0)."""
    import datetime

    values: dict[str, Any] = {
        "UID": overrides.get("uid", "evt-1"),
        "SUMMARY": overrides.get("summary", "Test Event"),
        "DESCRIPTION": overrides.get("description", ""),
        "LOCATION": overrides.get("location", ""),
        "DTSTART": MagicMock(
            dt=overrides.get("dtstart", datetime.datetime(2026, 6, 15, 9, 0, 0))
        ),
        "DTEND": MagicMock(
            dt=overrides.get("dtend", datetime.datetime(2026, 6, 15, 10, 0, 0))
        ),
    }
    comp = MagicMock()
    comp.get.side_effect = lambda name, default=None: values.get(name, default)
    obj = MagicMock()
    obj.icalendar_component = comp
    return obj


def _mock_vtodo(**overrides: Any) -> MagicMock:
    """Build a mock caldav object for a VTODO exposing ``icalendar_component``."""
    import datetime

    values: dict[str, Any] = {
        "UID": overrides.get("uid", "task-1"),
        "SUMMARY": overrides.get("summary", "Test Task"),
        "DESCRIPTION": overrides.get("description", ""),
        "DTSTART": MagicMock(
            dt=overrides.get("dtstart", datetime.datetime(2026, 6, 20, 8, 0, 0))
        ),
        "DUE": MagicMock(dt=overrides.get("due", datetime.date(2026, 6, 21))),
        "STATUS": overrides.get("status", "NEEDS-ACTION"),
    }
    comp = MagicMock()
    comp.get.side_effect = lambda name, default=None: values.get(name, default)
    obj = MagicMock()
    obj.icalendar_component = comp
    return obj


def _mock_vcard(**overrides: str) -> MagicMock:
    """Build a mock caldav object exposing raw vCard ``data`` (caldav 2.0)."""
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"UID:{overrides.get('uid', 'cnt-1')}",
        f"FN:{overrides.get('full_name', 'John Doe')}",
    ]
    if overrides.get("email"):
        lines.append(f"EMAIL:{overrides['email']}")
    if overrides.get("phone"):
        lines.append(f"TEL:{overrides['phone']}")
    if overrides.get("address"):
        lines.append(f"ADR:;;{overrides['address']};;;")
    lines.append("END:VCARD")
    obj = MagicMock()
    obj.data = "\n".join(lines) + "\n"
    return obj
