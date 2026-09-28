"""robotsix_calendar — calendar and contacts agent for Radicale.

This package provides a calendar and contacts management agent.  It parses
natural-language instructions via ``robotsix-llmio`` and executes
CalDAV/CardDAV operations against a Radicale server.
"""

from __future__ import annotations

from .agent import (  # noqa: F401 — re-exports for package namespace
    _DISPATCH,
    _OPERATION_NOUN,
    _OPERATION_VERB,
    CalDavClient,
    CalendarAgent,
    CalendarEvent,
    CalendarOperation,
    Contact,
    ContactOperation,
    IntentParseError,
    IntentParser,
    ParsedIntent,
    Task,
    TaskOperation,
    _render_reply,
    _summarize_item,
)
from .agent import __all__ as _agent_all
from .caldav_client.exceptions import (
    AgentLogicError,
    AuthError,
    CalDAVError,
    CalendarError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)

__all__ = [
    *_agent_all,
    "AgentLogicError",
    "AuthError",
    "CalDAVError",
    "CalendarError",
    "ConflictError",
    "NotFoundError",
    "RateLimitError",
    "__version__",
]

__version__ = "0.1.0"
