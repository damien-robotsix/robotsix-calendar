"""Unit tests for the Settings model and its validators."""

from __future__ import annotations

import json
import os
import tempfile

import pytest
from pydantic import SecretStr
from robotsix_config import load_config

from robotsix_calendar.settings import (
    COMPONENT_ALIAS,
    LangfuseProjectSettings,
    LangfuseSettings,
    OpenRouterSettings,
    Settings,
)

# ---------------------------------------------------------------------------
# _normalize_log_level
# ---------------------------------------------------------------------------


class TestNormalizeLogLevel:
    """Tests for the ``_normalize_log_level`` field validator."""

    def test_strips_whitespace(self) -> None:
        assert Settings._normalize_log_level("  debug  ") == "DEBUG"

    def test_lower_cases(self) -> None:
        assert Settings._normalize_log_level("info") == "INFO"

    def test_mixed_case_and_whitespace(self) -> None:
        assert Settings._normalize_log_level("  Warning  ") == "WARNING"

    def test_already_normalized(self) -> None:
        assert Settings._normalize_log_level("ERROR") == "ERROR"

    def test_invalid_level_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
            Settings._normalize_log_level("BOGUS")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write_config(data: dict) -> str:
    """Write a temporary config file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_settings_")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# Full Settings construction via load_config
# ---------------------------------------------------------------------------


class TestSettingsConstruction:
    """Tests exercising ``load_config(Settings, path=...)``."""

    def test_defaults(self) -> None:
        path = _write_config(
            {
                "RADICALE_URL": "https://radicale.example.com",
                "RADICALE_USERNAME": "user",
                "RADICALE_PASSWORD": "secret",  # pragma: allowlist secret
            }
        )
        s = load_config(Settings, path=path)
        assert s.RADICALE_URL == "https://radicale.example.com"
        assert s.RADICALE_USERNAME == "user"
        assert s.RADICALE_PASSWORD.get_secret_value() == "secret"
        assert s.RADICALE_DEFAULT_CALENDAR == "Robotsix"
        assert s.LOG_LEVEL == "INFO"
        assert s.JSON_LOGS is False

    def test_radicale_fields_from_config(self) -> None:
        path = _write_config(
            {
                "RADICALE_URL": "https://radicale.example.com",
                "RADICALE_USERNAME": "user",
                "RADICALE_PASSWORD": "secret",  # pragma: allowlist secret
            }
        )
        s = load_config(Settings, path=path)
        assert s.RADICALE_URL == "https://radicale.example.com"
        assert s.RADICALE_USERNAME == "user"
        assert s.RADICALE_PASSWORD.get_secret_value() == "secret"

    def test_radicale_default_calendar_from_config(self) -> None:
        path = _write_config(
            {
                "RADICALE_URL": "https://x.com",
                "RADICALE_USERNAME": "u",
                "RADICALE_PASSWORD": "p",  # pragma: allowlist secret
                "RADICALE_DEFAULT_CALENDAR": "Damien",
            }
        )
        s = load_config(Settings, path=path)
        assert s.RADICALE_DEFAULT_CALENDAR == "Damien"

    def test_radicale_default_calendar_defaults_to_robotsix(self) -> None:
        path = _write_config(
            {
                "RADICALE_URL": "https://x.com",
                "RADICALE_USERNAME": "u",
                "RADICALE_PASSWORD": "p",  # pragma: allowlist secret
            }
        )
        s = load_config(Settings, path=path)
        assert s.RADICALE_DEFAULT_CALENDAR == "Robotsix"

    def test_log_level_from_config(self) -> None:
        path = _write_config(
            {
                "RADICALE_URL": "https://x.com",
                "RADICALE_USERNAME": "u",
                "RADICALE_PASSWORD": "p",  # pragma: allowlist secret
                "LOG_LEVEL": "DEBUG",
            }
        )
        s = load_config(Settings, path=path)
        assert s.LOG_LEVEL == "DEBUG"

    def test_json_logs_from_config(self) -> None:
        path = _write_config(
            {
                "RADICALE_URL": "https://x.com",
                "RADICALE_USERNAME": "u",
                "RADICALE_PASSWORD": "p",  # pragma: allowlist secret
                "JSON_LOGS": True,
            }
        )
        s = load_config(Settings, path=path)
        assert s.JSON_LOGS is True

    def test_invalid_log_level_raises_during_load(self) -> None:
        path = _write_config({"LOG_LEVEL": "BOGUS"})
        from robotsix_config import InvalidConfigError

        with pytest.raises(InvalidConfigError):
            load_config(Settings, path=path)

    def test_extra_fields_are_rejected(self) -> None:
        path = _write_config({"UNKNOWN_VAR": "ignored"})
        from robotsix_config import InvalidConfigError

        with pytest.raises(InvalidConfigError):
            load_config(Settings, path=path)


# ---------------------------------------------------------------------------
# Component-alias drift enforcement
# ---------------------------------------------------------------------------


class TestCredentialAliasMatching:
    """Tests for the ``_check_credential_aliases_match`` model validator."""

    def _settings(
        self,
        langfuse_aliases: set[str],
        openrouter_aliases: set[str],
    ) -> Settings:
        langfuse = LangfuseSettings(
            host="https://langfuse.example.com",
            projects={
                alias: LangfuseProjectSettings(
                    public_key=SecretStr("pk"),
                    secret_key=SecretStr("sk"),
                )
                for alias in langfuse_aliases
            },
        )
        openrouter = OpenRouterSettings(
            keys={alias: SecretStr("sk-or") for alias in openrouter_aliases}
        )
        return Settings(
            RADICALE_URL="https://x.com",
            RADICALE_USERNAME="u",
            RADICALE_PASSWORD=SecretStr("p"),
            langfuse=langfuse,
            openrouter=openrouter,
        )

    def test_matching_aliases_are_accepted(self) -> None:
        settings = self._settings({COMPONENT_ALIAS}, {COMPONENT_ALIAS})
        assert settings.langfuse is not None
        assert COMPONENT_ALIAS in settings.langfuse.projects
        assert COMPONENT_ALIAS in settings.openrouter.keys

    def test_drifted_aliases_raise(self) -> None:
        with pytest.raises(ValueError, match="must be keyed by the same"):
            self._settings({COMPONENT_ALIAS}, {"other-alias"})

    def test_only_openrouter_block_is_accepted(self) -> None:
        settings = Settings(
            RADICALE_URL="https://x.com",
            RADICALE_USERNAME="u",
            RADICALE_PASSWORD=SecretStr("p"),
            openrouter=OpenRouterSettings(keys={COMPONENT_ALIAS: SecretStr("sk-or")}),
        )
        assert settings.langfuse is None
        assert COMPONENT_ALIAS in settings.openrouter.keys
