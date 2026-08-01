"""Unit tests for the Docker HEALTHCHECK probe."""

from __future__ import annotations

import pytest

from tests.healthcheck.conftest import _make_mock_client, _make_mock_settings

# ---------------------------------------------------------------------------
# main() — credential validation
# ---------------------------------------------------------------------------


class TestMainMissingCredentials:
    """``main()`` exits early when required credentials are missing."""

    @pytest.mark.parametrize(
        ("url", "username", "password"),
        [
            ("", "user", "pass"),
            ("https://x", "", "pass"),
            ("https://x", "user", ""),
        ],
    )
    def test_exits_code_1_when_credential_missing(
        self,
        url: str,
        username: str,
        password: str,
        healthcheck_main,
    ) -> None:
        settings = _make_mock_settings(url=url, username=username, password=password)
        excinfo, _output = healthcheck_main(settings=settings)
        assert excinfo.value.code == 1


# ---------------------------------------------------------------------------
# main() — success branches
# ---------------------------------------------------------------------------


class TestMainSuccess:
    """``main()`` exits 0 when the CalDAV server responds."""

    def test_success_on_first_attempt(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": True, "calendar_count": 3})
        excinfo, output = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert excinfo.value.code == 0
        assert "healthcheck OK:" in output.out
        assert "connected" in output.out


# ---------------------------------------------------------------------------
# main() — failure branches
# ---------------------------------------------------------------------------


class TestMainFailure:
    """``main()`` exits 1 when the CalDAV server is unreachable."""

    def test_failure_when_connected_false(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": False, "error": "refused"})
        excinfo, output = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert excinfo.value.code == 1
        assert "healthcheck FAILED" in output.err

    def test_exception_during_client_creation(self, healthcheck_main) -> None:
        excinfo, output = healthcheck_main(
            caldav_spec={"side_effect": ValueError("bad url")}
        )
        assert excinfo.value.code == 1
        assert "healthcheck FAILED" in output.err
