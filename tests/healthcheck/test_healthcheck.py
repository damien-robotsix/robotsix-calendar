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
        excinfo, _output, _retry_calls = healthcheck_main(settings=settings)
        assert excinfo.value.code == 1


# ---------------------------------------------------------------------------
# main() — success branches
# ---------------------------------------------------------------------------


class TestMainSuccess:
    """``main()`` exits 0 when the CalDAV server responds."""

    def test_success_on_first_attempt(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": True, "calendar_count": 3})
        excinfo, output, retry_calls = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert excinfo.value.code == 0
        assert "healthcheck OK:" in output.out
        assert "connected" in output.out
        assert len(retry_calls) == 1


# ---------------------------------------------------------------------------
# main() — failure branches
# ---------------------------------------------------------------------------


class TestMainFailure:
    """``main()`` exits 1 after all retries are exhausted."""

    def test_failure_when_connected_false(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": False, "error": "refused"})
        excinfo, output, _retry_calls = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert excinfo.value.code == 1
        assert "healthcheck FAILED after retries" in output.err

    def test_exception_during_client_creation(self, healthcheck_main) -> None:
        excinfo, output, _retry_calls = healthcheck_main(
            caldav_spec={"side_effect": ValueError("bad url")}
        )
        assert excinfo.value.code == 1
        assert "healthcheck FAILED after retries" in output.err


# ---------------------------------------------------------------------------
# main() — call_with_retry arguments
# ---------------------------------------------------------------------------


class TestMainCallWithRetry:
    """``call_with_retry`` is invoked with the correct arguments."""

    def test_passes_retry_config(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": True, "calendar_count": 1})
        _excinfo, _output, retry_calls = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert len(retry_calls) == 1
        call = retry_calls[0]
        assert call["what"] == "healthcheck"
        assert call["config"] is not None

    def test_passes_is_transient_fn_when_provided(self, healthcheck_main) -> None:
        client = _make_mock_client({"connected": True, "calendar_count": 1})
        _excinfo, _output, retry_calls = healthcheck_main(
            caldav_spec={"return_value": client}
        )
        assert len(retry_calls) == 1
        # No custom is_transient_fn passed for healthcheck (uses default)
        assert retry_calls[0]["is_transient_fn"] is None
