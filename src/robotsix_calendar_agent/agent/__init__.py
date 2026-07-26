"""CalendarAgent — calendar/contacts management agent.

Wires together :class:`IntentParser`, :class:`CalDavClient` into a
single runnable agent.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import asdict
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
        llm_model_config: Forwarded to :class:`IntentParser` for llmio
            model selection.

    Raises:
        ValueError: If Radicale credentials are missing in the config file.
    """

    def __init__(
        self,
        agent_id: str = "calendar",
        *,
        llm_model_config: dict[str, Any] | None = None,
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
        self._intent_parser = IntentParser(model_config=llm_model_config)

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


# ---------------------------------------------------------------------------
# dispatch infrastructure
# ---------------------------------------------------------------------------


def _build_event(params: dict[str, Any]) -> CalendarEvent:
    """Build a :class:`CalendarEvent` from parsed intent *params*."""
    return CalendarEvent(
        summary=params.get("summary", ""),
        description=params.get("description", ""),
        location=params.get("location", ""),
        dtstart=params.get("dtstart", ""),
        dtend=params.get("dtend", ""),
        calendar_id=params.get("calendar_id", ""),
    )


def _build_contact(params: dict[str, Any]) -> Contact:
    """Build a :class:`Contact` from parsed intent *params*."""
    return Contact(
        full_name=params.get("full_name", ""),
        email=params.get("email", ""),
        phone=params.get("phone", ""),
        address=params.get("address", ""),
        addressbook_id=params.get("addressbook_id", ""),
    )


def _entity_op(
    params: dict[str, Any],
    *,
    builder: Callable[[dict[str, Any]], Any],
    serializer: Callable[[Any], dict[str, Any]],
    create_fn: Callable[..., Any],
    update_fn: Callable[..., Any],
    id_key: str,
    operation: str | None = None,
) -> dict[str, Any]:
    """Generic helper for create/update handlers.

    Captures the common 3-step pattern:
    1. Build domain object from params.
    2. Call client CRUD method — create unless *operation* starts with
       ``"update"`` (dispatch is operation-based, never uid-based).
    3. Serialize result via serializer.
    """
    entity = builder(params)
    if operation and operation.startswith("update"):
        uid = params.get("uid", "")
        if not uid:
            raise AgentLogicError(
                "A UID is required to update, but none was provided.",
            )
        kwargs = {id_key: params.get(id_key, "")}
        result = update_fn(uid, entity, **kwargs)
    else:
        kwargs = {id_key: params.get(id_key, "")}
        result = create_fn(entity, **kwargs)
    return serializer(result)


def _delete_entity_op(
    params: dict[str, Any],
    *,
    delete_fn: Callable[..., None],
    id_key: str,
) -> dict[str, bool]:
    """Generic helper for delete handlers.

    Captures the common pattern:
    1. Validate uid is present and non-empty.
    2. Call client delete method.
    3. Return confirmation dict.
    """
    uid = params.get("uid", "")
    if not uid:
        raise AgentLogicError(
            "A UID is required to delete, but none was provided.",
        )
    kwargs: dict[str, Any] = {id_key: params.get(id_key, "")}
    delete_fn(uid=uid, **kwargs)
    return {"deleted": True}


def _handle_list_events(
    client: CalDavClient,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        asdict(e)
        for e in client.list_events(
            start=params.get("start", ""),
            end=params.get("end", ""),
            calendar_id=params.get("calendar_id", ""),
        )
    ]


def _handle_list_tasks(
    client: CalDavClient,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        asdict(t)
        for t in client.list_tasks(
            calendar_id=params.get("calendar_id", ""),
        )
    ]


def _handle_create_or_update_event(
    client: CalDavClient,
    params: dict[str, Any],
    operation: str = "",
) -> dict[str, Any]:
    return _entity_op(
        params,
        builder=_build_event,
        serializer=asdict,
        create_fn=client.create_event,
        update_fn=client.update_event,
        id_key="calendar_id",
        operation=operation,
    )


def _handle_list_calendars(
    client: CalDavClient,
    _params: dict[str, Any],
) -> list[str]:
    """Return the names of the user's available calendars."""
    return client.list_calendars()


def _handle_delete_event(
    client: CalDavClient,
    params: dict[str, Any],
) -> dict[str, bool]:
    return _delete_entity_op(
        params, delete_fn=client.delete_event, id_key="calendar_id"
    )


def _handle_list_contacts(
    client: CalDavClient,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        asdict(c)
        for c in client.list_contacts(addressbook_id=params.get("addressbook_id", ""))
    ]


def _handle_create_or_update_contact(
    client: CalDavClient,
    params: dict[str, Any],
    operation: str = "",
) -> dict[str, Any]:
    return _entity_op(
        params,
        builder=_build_contact,
        serializer=asdict,
        create_fn=client.create_contact,
        update_fn=client.update_contact,
        id_key="addressbook_id",
        operation=operation,
    )


def _handle_delete_contact(
    client: CalDavClient,
    params: dict[str, Any],
) -> dict[str, bool]:
    return _delete_entity_op(
        params, delete_fn=client.delete_contact, id_key="addressbook_id"
    )


_DISPATCH: dict[str, Callable[..., Any]] = {
    "list_events": _handle_list_events,
    "list_calendars": _handle_list_calendars,
    "create_event": lambda c, p: _handle_create_or_update_event(c, p, "create"),
    "update_event": lambda c, p: _handle_create_or_update_event(c, p, "update"),
    "delete_event": _handle_delete_event,
    "list_tasks": _handle_list_tasks,
    "list_contacts": _handle_list_contacts,
    "create_contact": lambda c, p: _handle_create_or_update_contact(c, p, "create"),
    "update_contact": lambda c, p: _handle_create_or_update_contact(c, p, "update"),
    "delete_contact": _handle_delete_contact,
}


def _summarize_item(item: dict[str, Any]) -> str:
    """One-line human summary of an event, task, or contact dict."""
    if isinstance(item, str):
        return item
    if "due" in item or "status" in item:  # task (VTODO)
        parts = [str(item.get("summary") or "(untitled)")]
        if item.get("due"):
            parts.append(f"due {item['due']}")
        if item.get("status"):
            parts.append(f"[{item['status']}]")
        line = " ".join(parts)
        return f"{line} [uid={item['uid']}]" if item.get("uid") else line
    if "summary" in item or "dtstart" in item:  # event
        parts = [str(item.get("summary") or "(untitled)")]
        if item.get("dtstart"):
            parts.append(f"at {item['dtstart']}")
        if item.get("location"):
            parts.append(f"({item['location']})")
        line = " ".join(parts)
        return f"{line} [uid={item['uid']}]" if item.get("uid") else line
    if "full_name" in item or "email" in item:  # contact
        name = str(item.get("full_name") or "(no name)")
        return f"{name} <{item['email']}>" if item.get("email") else name
    return json.dumps(item, default=str)


# Maps each operation to the human-readable noun used in "No <noun> found." replies.
_OPERATION_NOUN: dict[str, str] = {
    "list_events": "events",
    "list_calendars": "calendars",
    "list_tasks": "tasks",
    "list_contacts": "contacts",
}

# Maps each operation to the human-readable verb used in "<Verb>: …" replies.
_OPERATION_VERB: dict[str, str] = {
    "create_event": "Created",
    "create_contact": "Created",
    "update_event": "Updated",
    "update_contact": "Updated",
}


def _render_reply(operation: str, result: Any) -> str:
    """Render a human-readable reply string from a dispatch *result*.

    Generic consumers (e.g. robotsix-chat) read the reply via
    ``reply_text``, which looks for the ``"reply"`` key; the structured
    ``"result"`` is retained for programmatic consumers. Without this, those
    consumers see an empty reply and fall back to their default message.
    """
    if isinstance(result, dict) and result.get("deleted") is True:
        return "Done — the item was deleted."
    if isinstance(result, list):
        if not result:
            noun = _OPERATION_NOUN.get(operation, "items")
            return f"No {noun} found."
        lines = "\n".join(f"- {_summarize_item(i)}" for i in result)
        return f"Found {len(result)}:\n{lines}"
    if isinstance(result, dict):
        verb = _OPERATION_VERB.get(operation, "Result")
        return f"{verb}: {_summarize_item(result)}"
    return str(result)


_DISPATCH_KEYS = set(_DISPATCH)
_ENUM_VALUES = (
    {m.value for m in CalendarOperation}
    | {m.value for m in ContactOperation}
    | {m.value for m in TaskOperation}
)
assert _DISPATCH_KEYS == _ENUM_VALUES, (  # nosec B101 — import-time invariant check
    f"Mismatch: extra in dict={_DISPATCH_KEYS - _ENUM_VALUES}, "
    f"missing={_ENUM_VALUES - _DISPATCH_KEYS}"
)

# Every dispatch key that can reach _render_reply must have a noun or
# verb entry.  delete_event/delete_contact are handled by the
# "deleted": True branch and need neither.
_NOUN_VERB_KEYS = _OPERATION_NOUN.keys() | _OPERATION_VERB.keys()
assert (
    _NOUN_VERB_KEYS
    | {  # nosec B101
        "delete_event",
        "delete_contact",
    }
    == _DISPATCH_KEYS
), (
    "_OPERATION_NOUN / _OPERATION_VERB missing entries for: "
    f"{_DISPATCH_KEYS - _NOUN_VERB_KEYS - {'delete_event', 'delete_contact'}}"
)
