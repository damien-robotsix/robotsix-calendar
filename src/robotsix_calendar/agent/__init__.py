"""CalendarAgent — calendar/contacts management agent.

Wires together :class:`IntentParser`, :class:`CalDavClient` into a
single runnable agent.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from opentelemetry import trace

from ..caldav_client import (
    CalDavClient,
    CalendarEvent,
    Contact,
    Task,
)
from ..caldav_client.exceptions import AgentLogicError
from ..intent_parser import (
    CalendarOperation,
    ContactOperation,
    IntentParseError,
    IntentParser,
    ParsedIntent,
    TaskOperation,
)
from ..settings import COMPONENT_ALIAS, Settings


def _setup_tracing(settings: Settings | None = None) -> None:
    """Initialise Langfuse tracing from the canonical config block.

    Exports ``LANGFUSE_HOST``, ``LANGFUSE_PUBLIC_KEY`` and
    ``LANGFUSE_SECRET_KEY`` into the process environment (the
    OpenTelemetry SDK reads these at span-export time) **before**
    calling ``setup_langfuse_tracing``.

    When *settings* is ``None`` (module-load-time fallback), the
    function is a no-op — the canonical config is not available until
    :class:`CalendarAgent` is instantiated.
    """
    if settings is None or settings.langfuse is None:
        return

    langfuse_host = settings.langfuse.host
    if not isinstance(langfuse_host, str):
        return  # guard against MagicMock in test environments

    project = settings.langfuse.projects.get(COMPONENT_ALIAS)
    if project is None:
        return

    os.environ.setdefault("LANGFUSE_HOST", langfuse_host)
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", project.public_key.get_secret_value())
    os.environ.setdefault("LANGFUSE_SECRET_KEY", project.secret_key.get_secret_value())

    try:
        from robotsix_llmio.core import setup_langfuse_tracing  # pragma: no cover

        setup_langfuse_tracing()
    except ImportError:  # pragma: no cover
        pass


def _setup_openrouter_key(settings: Settings | None = None) -> None:
    """Export the canonical OpenRouter key into the process environment.

    The llmio OpenRouter provider reads ``OPENROUTER_API_KEY`` at
    construction time, so exporting it before any :class:`IntentParser`
    use ensures LLM calls use the canonical key from the config block.

    When *settings* is ``None`` the function is a no-op — the canonical
    config is not available.
    """
    if settings is None or settings.openrouter is None:
        return

    key = settings.openrouter.keys.get(COMPONENT_ALIAS)
    if key is None:
        return

    secret = key.get_secret_value()
    if not isinstance(secret, str):
        return  # guard against MagicMock in test environments

    os.environ.setdefault("OPENROUTER_API_KEY", secret)


def _setup_runtime_credentials(settings: Settings | None = None) -> None:
    """Initialise runtime LLM credentials before any llmio/SDK use.

    Exports the canonical Langfuse and OpenRouter credentials into the
    process environment and starts Langfuse tracing.  The deployed
    service entrypoint must invoke this before any :class:`IntentParser`
    (or other llmio/SDK) use — not only when :class:`CalendarAgent` is
    constructed.
    """
    _setup_tracing(settings)
    _setup_openrouter_key(settings)


logger = logging.getLogger(__name__)

_tracer = trace.get_tracer(__name__)

__all__ = [
    "CalDavClient",
    "CalendarAgent",
    "CalendarEvent",
    "CalendarOperation",
    "Contact",
    "ContactOperation",
    "IntentParseError",
    "IntentParser",
    "ParsedIntent",
    "Task",
    "TaskOperation",
]


class CalendarAgent:
    """Top-level agent that provides calendar/contact operations.

    Creates a :class:`CalDavClient` and :class:`IntentParser`.  The
    dispatch table (:func:`_dispatch`) maps parsed intents to CalDAV
    operations; callers can use it directly.

    Args:
        agent_id: Agent ID (default ``"calendar"``).
        root_settings: An existing :class:`Settings` instance.  When
            ``None`` (default), settings are loaded from the config
            file on construction.

    Raises:
        ValueError: If Radicale credentials are missing in the config file.
    """

    def __init__(
        self,
        agent_id: str = "calendar",
        root_settings: Settings | None = None,
    ) -> None:
        if root_settings is None:
            from robotsix_config import load_config

            from ..settings import Settings as _Settings

            settings = load_config(_Settings)
        else:
            settings = root_settings

        # -- Initialise runtime credentials from the canonical block ---
        _setup_runtime_credentials(settings)

        self._agent_id = agent_id

        url = settings.RADICALE_URL
        username = settings.RADICALE_USERNAME
        password = settings.RADICALE_PASSWORD.get_secret_value()

        if not url or not username or not password:
            _missing_credentials_msg = (
                "Radicale credentials are required. "
                "Provide RADICALE_URL, RADICALE_USERNAME, and "
                "RADICALE_PASSWORD in config/config.json."
            )
            raise ValueError(_missing_credentials_msg)

        self._caldav = CalDavClient(
            url,
            username,
            password,
            default_calendar=settings.RADICALE_DEFAULT_CALENDAR,
            timeout=settings.CALDAV_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, parsed: ParsedIntent) -> Any:
        """Route a parsed intent to the appropriate CalDavClient method."""
        op = parsed.operation
        params: dict[str, Any] = parsed.params

        logger.debug("Dispatching operation=%r params=%r", op, params)

        handler = _DISPATCH.get(op)
        if handler is None:
            raise AgentLogicError(
                f"Unknown operation: {op}",
            )

        with _tracer.start_as_current_span("agent.dispatch") as span:
            span.set_attribute("agent.operation", op)
            span.set_attribute("agent.agent_id", self._agent_id)
            return handler(self._caldav, params)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def __enter__(self) -> CalendarAgent:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


# Re-export private symbols from submodules so that tests and other
# consumers can continue importing from ``robotsix_calendar.agent``.
from ._dispatch import _DISPATCH  # noqa: E402
from ._reply import (  # noqa: E402, F401
    _OPERATION_NOUN,
    _OPERATION_VERB,
    _render_reply,
    _summarize_item,
)
