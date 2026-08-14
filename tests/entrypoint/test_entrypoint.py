"""Tests for the long-lived in-process entrypoint."""

from __future__ import annotations

import signal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

# ---------------------------------------------------------------------------
# Settings LOG_LEVEL validation
# ---------------------------------------------------------------------------


def test_log_level_validation_rejects_invalid() -> None:
    """Setting an invalid LOG_LEVEL must raise ValidationError."""
    from pydantic import ValidationError

    from robotsix_calendar_agent.settings import Settings

    with pytest.raises(ValidationError):
        Settings(
            RADICALE_URL="https://x.com",
            RADICALE_USERNAME="u",
            RADICALE_PASSWORD=SecretStr("p"),
            LOG_LEVEL="GARBAGE",
        )


def test_log_level_validation_normalises_case() -> None:
    """LOG_LEVEL must be normalised to uppercase."""
    from robotsix_calendar_agent.settings import Settings

    s = Settings(
        RADICALE_URL="https://x.com",
        RADICALE_USERNAME="u",
        RADICALE_PASSWORD=SecretStr("p"),
        LOG_LEVEL="debug",
    )
    assert s.LOG_LEVEL == "DEBUG"


class TestMain:
    def test_inprocess_blocks(self) -> None:
        from robotsix_calendar_agent import entrypoint

        with (
            patch("robotsix_calendar_agent.entrypoint._serve_blocking") as mock_serve,
            patch("robotsix_config.load_config"),
            patch("robotsix_llmio.logging.setup_logging"),
        ):
            entrypoint.main()

        mock_serve.assert_called_once_with()

    def test_setup_logging_called_with_expected_args(self) -> None:
        from robotsix_calendar_agent import entrypoint

        with (
            patch("robotsix_calendar_agent.entrypoint._serve_blocking"),
            patch("robotsix_config.load_config") as mock_load,
            patch("robotsix_llmio.logging.setup_logging") as mock_setup,
        ):
            mock_settings = MagicMock()
            mock_settings.LOG_LEVEL = "DEBUG"
            mock_settings.JSON_LOGS = True
            mock_load.return_value = mock_settings

            entrypoint.main()

        mock_setup.assert_called_once_with(
            level="DEBUG",
            fmt="json",
            loggers=("robotsix_calendar_agent",),
        )

    def test_runtime_credentials_setup_called_with_settings(self) -> None:
        from robotsix_calendar_agent import entrypoint

        with (
            patch("robotsix_calendar_agent.entrypoint._serve_blocking"),
            patch("robotsix_config.load_config") as mock_load,
            patch("robotsix_llmio.logging.setup_logging"),
            patch(
                "robotsix_calendar_agent.agent._setup_runtime_credentials"
            ) as mock_credentials,
        ):
            mock_settings = MagicMock()
            mock_load.return_value = mock_settings

            entrypoint.main()

        mock_credentials.assert_called_once_with(mock_settings)

    def test_setup_logging_console_fmt(self) -> None:
        from robotsix_calendar_agent import entrypoint

        with (
            patch("robotsix_calendar_agent.entrypoint._serve_blocking"),
            patch("robotsix_config.load_config") as mock_load,
            patch("robotsix_llmio.logging.setup_logging") as mock_setup,
        ):
            mock_settings = MagicMock()
            mock_settings.LOG_LEVEL = "INFO"
            mock_settings.JSON_LOGS = False
            mock_load.return_value = mock_settings

            entrypoint.main()

        mock_setup.assert_called_once_with(
            level="INFO",
            fmt="console",
            loggers=("robotsix_calendar_agent",),
        )


# ---------------------------------------------------------------------------
# _serve_blocking signal handling (in-process mode)
# ---------------------------------------------------------------------------


class TestServeBlocking:
    @pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
    def test_signal_triggers_stop_and_clean_exit(self, sig: int) -> None:
        from robotsix_calendar_agent import entrypoint

        handlers: dict[int, Any] = {}

        def fake_signal(signum: int, handler: Any) -> None:
            handlers[signum] = handler

        with (
            patch(
                "robotsix_calendar_agent.entrypoint.signal.signal",
                fake_signal,
            ),
            patch(
                "robotsix_calendar_agent.entrypoint.threading.Event"
            ) as mock_event_cls,
        ):

            def wait_side_effect(*_a: Any, **_k: Any) -> None:
                handlers[sig](sig, None)

            mock_event = mock_event_cls.return_value
            mock_event.wait.side_effect = wait_side_effect

            entrypoint._serve_blocking()

        mock_event.set.assert_called_once()
