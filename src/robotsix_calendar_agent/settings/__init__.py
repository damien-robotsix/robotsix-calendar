"""Single source of truth for application configuration.

Loaded from ``config/config.json`` (or ``ROBOTSIX_CONFIG_FILE``) via
:func:`robotsix_config.load_config`.  All fields have safe defaults so
a missing config file means "all defaults".
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

COMPONENT_ALIAS = "robotsix-calendar-agent"
"""Canonical component alias.

Single source of truth for the alias that keys both ``langfuse.projects``
and ``openrouter.keys``.  Referenced by the runtime credential setup so the
two credential maps and the source lookups can never silently drift apart.
"""

__all__ = [
    "COMPONENT_ALIAS",
    "LangfuseProjectSettings",
    "LangfuseSettings",
    "OpenRouterSettings",
    "Settings",
]


class LangfuseProjectSettings(BaseModel):
    """Credentials for a single Langfuse project for one component alias."""

    public_key: SecretStr = Field(
        description="Langfuse public key (telemetry SDK key)."
    )

    secret_key: SecretStr = Field(
        description="Langfuse secret key (telemetry SDK secret)."
    )

    project_id: str = Field(
        default="",
        description=(
            "Optional project identifier override; empty means the public key scope."
        ),
    )


class LangfuseSettings(BaseModel):
    """Canonical Langfuse observability block.

    One project entry per LLM-facing component alias so the deployment
    engine can enumerate and reconcile credential coverage.
    """

    host: str = Field(
        description="Langfuse server host (e.g. https://langfuse.example.com)."
    )

    projects: dict[str, LangfuseProjectSettings] = Field(
        description=(
            "Map of component alias → project credentials.  Every component "
            "that emits LLM traffic must have an entry here keyed by the same "
            "alias used in ``openrouter.keys``."
        )
    )


class OpenRouterSettings(BaseModel):
    """Canonical OpenRouter credentials block.

    One key per LLM-facing component alias, matching the aliases
    declared in ``langfuse.projects``.
    """

    keys: dict[str, SecretStr] = Field(
        description="Map of component alias → OpenRouter API key for that component."
    )


class Settings(BaseModel):
    """Application settings loaded from ``config/config.json``.

    Located via the ``ROBOTSIX_CONFIG_FILE`` environment variable (or
    the default ``config/config.json``).  All values live in the config
    file — no environment overlay, no CLI merge.
    """

    model_config = {"extra": "forbid"}

    # -- Radicale credentials ------------------------------------------------
    RADICALE_URL: str = Field(
        description="Radicale server URL (e.g. https://radicale.example.com)."
    )

    RADICALE_USERNAME: str = Field(description="Radicale username for authentication.")

    RADICALE_PASSWORD: SecretStr = Field(
        description="Radicale password for authentication."
    )

    RADICALE_DEFAULT_CALENDAR: str = Field(
        default="Robotsix",
        description="Default calendar name when no calendar_id is provided.",
    )

    CALDAV_TIMEOUT: int = Field(
        default=30, description="Timeout in seconds for CalDAV HTTP requests."
    )

    CALDAV_HEALTHCHECK_TIMEOUT: int = Field(
        default=5,
        description=(
            "Timeout in seconds for the Docker HEALTHCHECK probe's CalDAV "
            "request. Keep this well under Docker's ``--timeout=10s`` so the "
            "probe exits before Docker kills it. Docker's own ``--retries`` "
            "and ``--interval`` provide transient-failure recovery across "
            "healthcheck invocations."
        ),
    )

    # -- LLM credential blocks (canonical) ------------------------------------
    langfuse: LangfuseSettings | None = Field(
        default=None,
        description=(
            "Langfuse observability credentials — host and per-alias project "
            "keys. Every component that emits LLM traffic must declare its "
            "projects here so the deployment engine can enumerate credential "
            "coverage."
        ),
    )

    openrouter: OpenRouterSettings | None = Field(
        default=None,
        description=(
            "OpenRouter API credentials — per-alias keys. Every component "
            "that emits LLM traffic must have an entry whose alias matches "
            "the corresponding ``langfuse.projects`` key."
        ),
    )

    # -- Logging -------------------------------------------------------------
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Log level - one of DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )

    JSON_LOGS: bool = Field(
        default=False,
        description="When True, emit logs as JSON for structured-log ingestion.",
    )

    # -- Validators ----------------------------------------------------------

    @field_validator("LOG_LEVEL")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        """Normalise to uppercase and reject invalid log levels."""
        v = v.strip().upper()
        if v not in logging.getLevelNamesMapping():
            raise ValueError(
                f"Invalid LOG_LEVEL={v!r}; must be one of "
                f"{sorted(logging.getLevelNamesMapping())}"
            )
        return v

    @model_validator(mode="after")
    def _check_credential_aliases_match(self) -> Settings:
        """Enforce that Langfuse and OpenRouter maps share the same aliases.

        Both blocks are optional, but when both are supplied they must be
        keyed by the same component aliases.  Otherwise ``_setup_tracing``
        and ``_setup_openrouter_key`` silently no-op for the drifted alias.
        """
        if self.langfuse is None or self.openrouter is None:
            return self

        langfuse_aliases = set(self.langfuse.projects)
        openrouter_aliases = set(self.openrouter.keys)
        if langfuse_aliases != openrouter_aliases:
            raise ValueError(
                "langfuse.projects and openrouter.keys must be keyed by the "
                "same component aliases; missing in langfuse: "
                f"{sorted(openrouter_aliases - langfuse_aliases)}, "
                "missing in openrouter: "
                f"{sorted(langfuse_aliases - openrouter_aliases)}"
            )
        return self
