"""Reply rendering for the CalendarAgent.

Formats dispatch results into human-readable reply strings.
"""

import json
from typing import Any

from ._dispatch import _DISPATCH


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
    "create_task": "Created",
    "update_event": "Updated",
    "update_contact": "Updated",
    "update_task": "Updated",
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


# ---------------------------------------------------------------------------
# import-time invariant: ensure every dispatch key that can reach
# _render_reply has a noun or verb entry
# ---------------------------------------------------------------------------

# Every dispatch key that can reach _render_reply must have a noun or
# verb entry.  delete_event/delete_contact are handled by the
# "deleted": True branch and need neither.
_NOUN_VERB_KEYS = _OPERATION_NOUN.keys() | _OPERATION_VERB.keys()
_DELETE_KEYS = {"delete_event", "delete_contact", "delete_task"}
_DISPATCH_KEYS = set(_DISPATCH)
assert (
    _NOUN_VERB_KEYS | _DELETE_KEYS  # nosec B101
    == _DISPATCH_KEYS
), (
    "_OPERATION_NOUN / _OPERATION_VERB missing entries for: "
    f"{_DISPATCH_KEYS - _NOUN_VERB_KEYS - _DELETE_KEYS}"
)
