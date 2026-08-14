# vulture whitelist — symbols listed here are excluded from dead-code detection.
# Add false-positive names one per line (bare names, not strings).

# Set in __init__ and used via self._url
_ = _url

# StrEnum members — used via the enum class, invisible to vulture
_ = LIST_EVENTS
_ = LIST_CALENDARS
_ = CREATE_EVENT
_ = UPDATE_EVENT
_ = DELETE_EVENT
_ = LIST_TASKS
_ = LIST_CONTACTS
_ = CREATE_CONTACT
_ = UPDATE_CONTACT
_ = DELETE_CONTACT
_ = CREATE_TASK
_ = UPDATE_TASK
_ = DELETE_TASK

# Dataclass field with default
_ = original_text

# Task dataclass fields with defaults — used via attribute access
_ = due
_ = status

# Pydantic field-validator methods — invoked by the framework, not dead code
_ = _normalize_log_level
_ = cls

# logging.Formatter subclass — format() called by logging framework internals
_ = format

# CalDavClient health probe — public API called on-demand by monitor;
# monitor_snapshot was removed but health is kept as public API
_ = health

# CalendarAgent attributes/methods — used by removed broker integration;
# kept as public API / still exercised in unit tests
_ = _dispatch
_ = _render_reply

# IntentParser.parse — public API method; the only in-tree consumer
# (add_to_calendar_handler.py) was removed, but external callers rely on it.
_ = parse

# CalendarError.code — public attribute set in __init__; the only in-tree
# consumer (add_to_calendar_handler.py's exc.code check) was removed.
_ = code

# Canonical credential blocks — field access by deployment engine / settings
# panel, not by application code
_ = project_id
_ = openrouter
