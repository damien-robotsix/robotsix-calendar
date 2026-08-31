"""Shared pytest fixtures and helpers for CalendarAgent tests."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import HealthCheck, settings

# Re-export the session-scoped integration fixture so it is explicitly
# available to all test modules.
from tests.caldav_client.caldav_test_server import caldav_client  # noqa: F401

# ---------------------------------------------------------------------------
# Hypothesis profile registration
# ---------------------------------------------------------------------------
settings.register_profile(
    "ci",
    max_examples=200,
    derandomize=True,
    deadline=None,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "dev",
    max_examples=50,
    deadline=5000,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
# In CI (GitHub Actions sets CI=true) default to the 'ci' profile;
# locally default to 'dev'.  HYPOTHESIS_PROFILE env var always wins
# when explicitly set.
_default_profile = "ci" if os.getenv("CI") == "true" else "dev"
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", _default_profile))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_temp_config(overrides: dict[str, Any] | None = None) -> str:
    """Write a temporary config.json and return its path.

    Fills in minimal Radicale credentials so CalendarAgent can be
    constructed without hitting the real Radicale.
    """
    data: dict[str, Any] = {
        "RADICALE_URL": "https://radicale.example.com",
        "RADICALE_USERNAME": "user",
        "RADICALE_PASSWORD": "pass",  # pragma: allowlist secret
        "RADICALE_DEFAULT_CALENDAR": "Robotsix",
        "CALDAV_TIMEOUT": 30,
        "LOG_LEVEL": "INFO",
        "JSON_LOGS": False,
    }
    if overrides:
        data.update(overrides)
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_config_")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_env() -> None:
    """Remove config-file env var so tests don't leak state."""
    os.environ.pop("ROBOTSIX_CONFIG_FILE", None)


@pytest.fixture
def calendar_agent() -> Any:
    """Create a CalendarAgent with all external deps mocked.

    The returned agent has ``_mock_parser`` and ``_mock_caldav``
    attributes attached for test assertions.
    """
    with (
        patch(
            "robotsix_calendar.agent.CalDavClient",
            autospec=True,
        ) as mock_caldav,
        patch(
            "robotsix_calendar.agent.IntentParser",
            autospec=True,
        ) as mock_parser_cls,
        patch(
            "robotsix_config.load_config",
        ),
    ):
        mock_parser = MagicMock()
        mock_parser_cls.return_value = mock_parser

        config_path = _write_temp_config()
        os.environ["ROBOTSIX_CONFIG_FILE"] = config_path

        from robotsix_calendar.agent import CalendarAgent

        agent = CalendarAgent()
        agent._mock_parser = mock_parser  # type: ignore[attr-defined]
        agent._mock_caldav = mock_caldav.return_value  # type: ignore[attr-defined]

        yield agent

        Path(config_path).unlink(missing_ok=True)
