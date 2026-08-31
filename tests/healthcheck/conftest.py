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
    settings.radicale_url = url
    settings.radicale_username = username
    settings.radicale_password = SecretStr(password)
    settings.radicale_default_calendar = default_calendar
    settings.caldav_timeout = 30
    settings.caldav_healthcheck_timeout = 5
    return settings


def _make_mock_client(health_result: dict[str, Any]) -> MagicMock:
    """Return a MagicMock CalDavClient with :meth:`health` stubbed."""
    client = MagicMock()
    client.health.return_value = health_result
    return client


@pytest.fixture
def healthcheck_main(capsys: pytest.CaptureFixture[str]):
    """Factory fixture to run ``healthcheck.main()`` with patched dependencies.

    Returns a callable that accepts ``settings=`` and ``caldav_spec=``
    keyword arguments and returns ``(excinfo, capsys_output)``.

    *settings* — a mock Settings object (defaults to a valid one).
    *caldav_spec* — dict of kwargs forwarded to ``patch("...CalDavClient", ...)``.
    """

    from robotsix_calendar.healthcheck import main as _main

    def _run(
        *,
        settings: MagicMock | None = None,
        caldav_spec: dict[str, Any] | None = None,
    ) -> tuple[Any, Any]:
        if settings is None:
            settings = _make_mock_settings()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "robotsix_calendar.healthcheck.load_config",
                    return_value=settings,
                )
            )

            if caldav_spec is not None:
                stack.enter_context(
                    patch(
                        "robotsix_calendar.healthcheck.CalDavClient",
                        **caldav_spec,
                    )
                )

            excinfo = stack.enter_context(pytest.raises(SystemExit))
            _main()

        return excinfo, capsys.readouterr()

    return _run
