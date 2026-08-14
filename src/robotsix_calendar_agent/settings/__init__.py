"""Single source of truth for application configuration.

Loaded from ``config/config.json`` (or ``ROBOTSIX_CONFIG_FILE``) via
:func:`robotsix_config.load_config`.  All fields have safe defaults so
a missing config file means "all defaults".
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, SecretStr, field_validator

__all__ = [
    "LangfuseProjectSettings",
    "LangfuseSettings",
    "OpenRouterSettings",
    "Settings",
]


class LangfuseProjectSettings(BaseModel):
    """Credentials for a single Langfuse project for one component alias."""

    public_key: SecretStr
    """Langfuse public key (telemetry SDK key)."""

    secret_key: SecretStr
    """Langfuse secret key (telemetry SDK secret)."""

    project_id: str = ""
    """Optional project identifier override; empty means the public key scope."""


class LangfuseSettings(BaseModel):
    """Canonical Langfuse observability block.

    One project entry per LLM-facing component alias so the deployment
    engine can enumerate and reconcile credential coverage.
    """

    host: str
    """Langfuse server host (e.g. https://langfuse.example.com)."""

    projects: dict[str, LangfuseProjectSettings]
    """Map of component alias → project credentials.  Every component
    that emits LLM traffic must have an entry here keyed by the same
    alias used in ``openrouter.keys``.
    """


class OpenRouterSettings(BaseModel):
    """Canonical OpenRouter credentials block.

    One key per LLM-facing component alias, matching the aliases
    declared in ``langfuse.projects``.
    """

    keys: dict[str, SecretStr]
    """Map of component alias → OpenRouter API key for that component."""


class Settings(BaseModel):
    """Application settings loaded from ``config/config.json``.

    Located via the ``ROBOTSIX_CONFIG_FILE`` environment variable (or
    the default ``config/config.json``).  All values live in the config
    file — no environment overlay, no CLI merge.
    """

    model_config = {"extra": "forbid"}

    # -- Radicale credentials ------------------------------------------------
    RADICALE_URL: str
    """Radicale server URL (e.g. https://radicale.example.com)."""

    RADICALE_USERNAME: str
    """Radicale username for authentication."""

    RADICALE_PASSWORD: SecretStr
    """Radicale password for authentication."""

    RADICALE_DEFAULT_CALENDAR: str = "Robotsix"
    """Default calendar name when no calendar_id is provided."""

    CALDAV_TIMEOUT: int = 30
    """Timeout in seconds for CalDAV HTTP requests."""

    CALDAV_HEALTHCHECK_TIMEOUT: int = 5
    """Timeout in seconds for the Docker HEALTHCHECK probe's CalDAV request.

    Keep this well under Docker's ``--timeout=10s`` so the probe exits
    before Docker kills it. Docker's own ``--retries`` and ``--interval``
    provide transient-failure recovery across healthcheck invocations.
    """

    # -- LLM credential blocks (canonical) ------------------------------------
    langfuse: LangfuseSettings | None = None
    """Langfuse observability credentials — host and per-alias project keys.

    Every component that emits LLM traffic must declare its projects here
    so the deployment engine can enumerate credential coverage.
    """

    openrouter: OpenRouterSettings | None = None
    """OpenRouter API credentials — per-alias keys.

    Every component that emits LLM traffic must have an entry whose alias
    matches the corresponding ``langfuse.projects`` key.
    """

    # -- Logging -------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    """Log level - one of DEBUG, INFO, WARNING, ERROR, CRITICAL."""

    JSON_LOGS: bool = False
    """When True, emit logs as JSON for structured-log ingestion."""

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
