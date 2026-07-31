"""CalendarAgent — calendar/contacts management agent.

Wires together :class:`IntentParser`, :class:`CalDavClient` into a
single runnable agent.
"""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import trace

try:
    from robotsix_llmio.core import setup_langfuse_tracing  # pragma: no cover

    setup_langfuse_tracing()
except ImportError:  # pragma: no cover
    pass

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

    Raises:
        ValueError: If Radicale credentials are missing in the config file.
    """

    def __init__(
        self,
        agent_id: str = "calendar",
    ) -> None:
        from robotsix_config import load_config

        from ..settings import Settings

        settings = load_config(Settings)

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
# consumers can continue importing from ``robotsix_calendar_agent.agent``.
from ._dispatch import _DISPATCH  # noqa: E402
from ._reply import (  # noqa: E402, F401
    _OPERATION_NOUN,
    _OPERATION_VERB,
    _render_reply,
    _summarize_item,
)
