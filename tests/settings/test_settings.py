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
        with pytest.raises(ValueError, match="Invalid log_level"):
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
                "radicale_url": "https://radicale.example.com",
                "radicale_username": "user",
                "radicale_password": "secret",  # pragma: allowlist secret
            }
        )
        s = load_config(Settings, path=path)
        assert s.radicale_url == "https://radicale.example.com"
        assert s.radicale_username == "user"
        assert s.radicale_password.get_secret_value() == "secret"
        assert s.radicale_default_calendar == "Robotsix"
        assert s.log_level == "INFO"
        assert s.json_logs is False

    def test_radicale_fields_from_config(self) -> None:
        path = _write_config(
            {
                "radicale_url": "https://radicale.example.com",
                "radicale_username": "user",
                "radicale_password": "secret",  # pragma: allowlist secret
            }
        )
        s = load_config(Settings, path=path)
        assert s.radicale_url == "https://radicale.example.com"
        assert s.radicale_username == "user"
        assert s.radicale_password.get_secret_value() == "secret"

    def test_radicale_default_calendar_from_config(self) -> None:
        path = _write_config(
            {
                "radicale_url": "https://x.com",
                "radicale_username": "u",
                "radicale_password": "p",  # pragma: allowlist secret
                "radicale_default_calendar": "Damien",
            }
        )
        s = load_config(Settings, path=path)
        assert s.radicale_default_calendar == "Damien"

    def test_radicale_default_calendar_defaults_to_robotsix(self) -> None:
        path = _write_config(
            {
                "radicale_url": "https://x.com",
                "radicale_username": "u",
                "radicale_password": "p",  # pragma: allowlist secret
            }
        )
        s = load_config(Settings, path=path)
        assert s.radicale_default_calendar == "Robotsix"

    def test_log_level_from_config(self) -> None:
        path = _write_config(
            {
                "radicale_url": "https://x.com",
                "radicale_username": "u",
                "radicale_password": "p",  # pragma: allowlist secret
                "log_level": "DEBUG",
            }
        )
        s = load_config(Settings, path=path)
        assert s.log_level == "DEBUG"

    def test_json_logs_from_config(self) -> None:
        path = _write_config(
            {
                "radicale_url": "https://x.com",
                "radicale_username": "u",
                "radicale_password": "p",  # pragma: allowlist secret
                "json_logs": True,
            }
        )
        s = load_config(Settings, path=path)
        assert s.json_logs is True

    def test_invalid_log_level_raises_during_load(self) -> None:
        path = _write_config({"log_level": "BOGUS"})
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
            radicale_url="https://x.com",
            radicale_username="u",
            radicale_password=SecretStr("p"),
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
            radicale_url="https://x.com",
            radicale_username="u",
            radicale_password=SecretStr("p"),
            openrouter=OpenRouterSettings(keys={COMPONENT_ALIAS: SecretStr("sk-or")}),
        )
        assert settings.langfuse is None
        assert COMPONENT_ALIAS in settings.openrouter.keys
