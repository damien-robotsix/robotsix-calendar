"""Fixtures for healthcheck tests."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr


def _make_mock_settings(
    url: str = "https://radicale.example.com",
    username: str = "user",
    password: str = "pass",  # noqa: S107
    default_calendar: str = "cal",
) -> MagicMock:
    """Return a MagicMock Settings with the given credential fields."""
    settings = MagicMock()
    settings.RADICALE_URL = url
    settings.RADICALE_USERNAME = username
    settings.RADICALE_PASSWORD = SecretStr(password)
    settings.RADICALE_DEFAULT_CALENDAR = default_calendar
    settings.CALDAV_TIMEOUT = 30
    return settings


def _make_mock_client(health_result: dict[str, Any]) -> MagicMock:
    """Return a MagicMock CalDavClient with :meth:`health` stubbed."""
    client = MagicMock()
    client.health.return_value = health_result
    return client


def _simulate_call_with_retry(
    fn: Any,
    *,
    config: Any = None,
    is_transient_fn: Any = None,
    what: str = "operation",
) -> Any:
    """Simulate :func:`robotsix_http.retry.call_with_retry` by calling ``fn`` once.

    Tracks calls so tests can inspect arguments.
    """
    _simulate_call_with_retry.calls.append(
        {
            "fn": fn,
            "config": config,
            "is_transient_fn": is_transient_fn,
            "what": what,
        }
    )
    return fn()


_simulate_call_with_retry.calls: list[dict[str, Any]] = []


@pytest.fixture
def healthcheck_main(capsys: pytest.CaptureFixture[str]):
    """Factory fixture to run ``healthcheck.main()`` with patched dependencies.

    Returns a callable that accepts ``settings=`` and ``caldav_spec=``
    keyword arguments and returns ``(excinfo, capsys_output, retry_calls)``.

    *settings* — a mock Settings object (defaults to a valid one).
    *caldav_spec* — dict of kwargs forwarded to ``patch("...CalDavClient", ...)``.
    When ``caldav_spec`` is not None, ``call_with_retry`` is also patched
    with a simulator that records every call.
    """

    from robotsix_calendar_agent.healthcheck import main as _main

    _simulate_call_with_retry.calls.clear()

    def _run(
        *,
        settings: MagicMock | None = None,
        caldav_spec: dict[str, Any] | None = None,
    ) -> tuple[Any, Any, list[dict[str, Any]]]:
        if settings is None:
            settings = _make_mock_settings()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "robotsix_calendar_agent.healthcheck.load_config",
                    return_value=settings,
                )
            )

            if caldav_spec is not None:
                stack.enter_context(
                    patch(
                        "robotsix_calendar_agent.healthcheck.CalDavClient",
                        **caldav_spec,
                    )
                )
                stack.enter_context(
                    patch(
                        "robotsix_calendar_agent.healthcheck.call_with_retry",
                        side_effect=_simulate_call_with_retry,
                    )
                )

            excinfo = stack.enter_context(pytest.raises(SystemExit))
            _main()

        return excinfo, capsys.readouterr(), list(_simulate_call_with_retry.calls)

    return _run
