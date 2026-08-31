"""Tests for caldav exception handling — auth, transport, mapping."""

from __future__ import annotations

import pytest

from robotsix_calendar.caldav_client import (
    CalDavClient,
)
from robotsix_calendar.caldav_client.exceptions import (
    AuthError,
    CalDAVError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)

# Re-use the shared _mock_caldav from conftest so that tests which set
# side_effects directly (TestAuthFailure, TestConnectFailure) operate on
# the same mock object that the autouse reset_mock_caldav fixture injects
# into sys.modules.
from tests.caldav_client.conftest import _make_event, _mock_caldav, _mock_vevent

# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class TestAuthFailure:
    def test_raises_auth_failed_on_authorization_error(self) -> None:
        _mock_caldav.DAVClient.side_effect = _mock_caldav.error.AuthorizationError(
            "bad creds"
        )

        with pytest.raises(AuthError) as exc_info:
            CalDavClient("https://x.com", "user", "wrong")
        assert exc_info.value.code == "auth_failed"


class TestTransportFailure:
    def test_raises_caldav_error_on_transport_exception(
        self, client: CalDavClient
    ) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.search.side_effect = Exception("connection refused")

        with pytest.raises(CalDAVError) as exc_info:
            client.list_events("2026-01-01", "2026-01-31")
        assert exc_info.value.code == "caldav_error"

    def test_retries_transient_failures_then_succeeds(
        self, client: CalDavClient
    ) -> None:
        """Verify retry actually kicks in: fail twice, succeed on third attempt."""
        cal = client._principal.calendars.return_value[0]
        cal.search.side_effect = [
            Exception("connection refused"),
            Exception("connection reset"),
            [_mock_vevent(uid="evt-1")],
        ]

        result = client.list_events("2026-01-01", "2026-01-31")

        assert len(result) == 1
        assert result[0].uid == "evt-1"
        assert cal.search.call_count == 3


class TestConnectFailure:
    def test_raises_caldav_error_on_generic_connect_exception(self) -> None:
        _mock_caldav.DAVClient.side_effect = Exception("connection refused")

        with pytest.raises(CalDAVError) as exc_info:
            CalDavClient("https://x.com", "user", "pass")
        assert exc_info.value.code == "caldav_error"


# ---------------------------------------------------------------------------
# caldav exception → CalendarError subclass mapping in _wrap_caldav_op
# ---------------------------------------------------------------------------


class TestCaldavExceptionMapping:
    """Verify that caldav-specific exceptions are mapped to distinct types."""

    def test_not_found_error_maps_to_not_found(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.side_effect = client._caldav.lib.error.NotFoundError(
            "resource not found"
        )
        with pytest.raises(NotFoundError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "not_found"

    def test_rate_limit_error_maps_to_rate_limited(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.side_effect = client._caldav.lib.error.RateLimitError(
            "too many requests"
        )
        with pytest.raises(RateLimitError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "rate_limited"

    def test_etag_mismatch_error_maps_to_conflict(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.side_effect = client._caldav.lib.error.EtagMismatchError(
            "ETag changed"
        )
        with pytest.raises(ConflictError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "conflict"

    def test_authorization_error_maps_to_auth_failed(
        self, client: CalDavClient
    ) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.side_effect = client._caldav.lib.error.AuthorizationError(
            "bad credentials"
        )
        with pytest.raises(AuthError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "auth_failed"

    def test_generic_exception_still_maps_to_caldav_error(
        self, client: CalDavClient
    ) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.side_effect = ValueError("something unexpected")
        with pytest.raises(CalDAVError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "caldav_error"
