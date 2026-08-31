"""Dispatch infrastructure for the CalendarAgent.

Maps parsed intents to CalDAV operations via a dispatch table.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from ..caldav_client import CalDavClient, CalendarEvent, Contact, Task
from ..caldav_client.exceptions import AgentLogicError
from ..intent_parser import CalendarOperation, ContactOperation, TaskOperation


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


def _build_task(params: dict[str, Any]) -> Task:
    """Build a :class:`Task` from parsed intent *params*."""
    return Task(
        summary=params.get("summary", ""),
        description=params.get("description", ""),
        dtstart=params.get("dtstart", ""),
        due=params.get("due", ""),
        status=params.get("status", ""),
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


def _handle_create_or_update_task(
    client: CalDavClient,
    params: dict[str, Any],
    operation: str = "",
) -> dict[str, Any]:
    return _entity_op(
        params,
        builder=_build_task,
        serializer=asdict,
        create_fn=client.create_task,
        update_fn=client.update_task,
        id_key="calendar_id",
        operation=operation,
    )


def _handle_delete_task(
    client: CalDavClient,
    params: dict[str, Any],
) -> dict[str, bool]:
    return _delete_entity_op(params, delete_fn=client.delete_task, id_key="calendar_id")


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
    "create_task": lambda c, p: _handle_create_or_update_task(c, p, "create"),
    "update_task": lambda c, p: _handle_create_or_update_task(c, p, "update"),
    "delete_task": _handle_delete_task,
}


# ---------------------------------------------------------------------------
# import-time invariant: ensure _DISPATCH covers every operation enum value
# ---------------------------------------------------------------------------

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
