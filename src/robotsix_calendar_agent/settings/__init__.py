"""Single source of truth for application configuration.

Loaded from ``config/config.json`` (or ``ROBOTSIX_CONFIG_FILE``) via
:func:`robotsix_config.load_config`.  All fields have safe defaults so
a missing config file means "all defaults".
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, SecretStr, field_validator


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
