"""``GET /chat-skill`` — SKILL.md endpoint for the robotsix-chat agent.

Serves a skill document teaching the chat agent how to drive the
calendar, task, contact, and calendar-listing API that this component
exposes.  The text is versioned with the app (no detached doc) so it
stays in sync with the actual route definitions in
:mod:`robotsix_calendar.api`.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["ChatSkill"])

_CHAT_SKILL_TEXT = """\
---
name: robotsix-calendar
description: Manage calendar events, tasks, and contacts on a Radicale CalDAV server.
---

## robotsix-calendar — Chat Agent Skill

You are connected to a **robotsix-calendar** component API backed by a
Radicale CalDAV/CardDAV server.  Use the endpoints below to list
calendars, and to read and manage calendar events, tasks, and contacts.

All requests and responses are JSON.  Dates and datetimes are ISO 8601
strings (e.g. `2026-09-01T10:00:00`).  The component adds **no
authentication itself** — access is granted by the central gateway that
fronts it.

### Base URL

The base URL is the same host and port used to serve this skill
document.  If you fetched the skill from
`http://<host>:8080/chat-skill`, use `http://<host>:8080` as the base.

---

## Errors

Every endpoint maps errors to a JSON body `{"detail": ..., "code": ...}`
with an HTTP status code:

| Status | Meaning |
| ------ | ------- |
| 401    | Radically authentication failure (`AuthError`) |
| 404    | Object not found (`NotFoundError`) |
| 409    | Conflict (e.g. duplicate / state conflict, `ConflictError`) |
| 429    | Rate limited (`RateLimitError`) |
| 502    | Upstream Radicale server error / 5xx (`CalDAVError`) |

---

## Calendars

### GET /calendars — list calendars

```
GET /calendars
```

Returns a JSON array of `{"name": "<calendar-name>"}` for every calendar
the configured account can see.  Use these `name` values as
`calendar_id` in the event and task endpoints below.

---

## Events

### Get events in a range

```
GET /events?start=<ISO8601>&end=<ISO8601>&calendar_id=<optional>
```

Query parameters:
- `start` — required, ISO 8601 range start.
- `end` — required, ISO 8601 range end.
- `calendar_id` — optional calendar name to restrict to.

Returns a JSON array of event objects:

```json
{
  "uid": "<unique id>",
  "summary": "Meeting",
  "description": "Team meeting",
  "location": "Office",
  "dtstart": "2026-09-01T10:00:00",
  "dtend": "2026-09-01T11:00:00",
  "calendar_id": "<calendar-name>"
}
```

### POST /events — create an event

```
POST /events
Content-Type: application/json

{
  "summary": "Meeting",
  "description": "Team meeting",
  "location": "Office",
  "dtstart": "2026-09-01T10:00:00",
  "dtend": "2026-09-01T11:00:00",
  "calendar_id": "<optional>"
}
```

Returns `201` with the created event object.  `summary`, `dtstart`, and
`dtend` are required; `description`, `location`, and `calendar_id`
default to `""` when omitted.

### PUT /events/{uid} — update an event

```
PUT /events/<uid>
Content-Type: application/json

{
  "summary": "...",
  "description": "...",
  "location": "...",
  "dtstart": "2026-09-01T10:00:00",
  "dtend": "2026-09-01T11:00:00",
  "calendar_id": "<optional>"
}
```

Replaces the event identified by `uid` with the supplied fields and
returns the updated event object.

### DELETE /events/{uid} — delete an event

```
DELETE /events/<uid>?calendar_id=<optional>
```

Deletes the event (idempotent).  Returns `204` with no body.

---

## Tasks

### GET /tasks — list tasks

```
GET /tasks?calendar_id=<optional>
```

Returns a JSON array of task objects:

```json
{
  "uid": "<unique id>",
  "summary": "Write report",
  "description": "",
  "dtstart": "",
  "due": "2026-09-05T17:00:00",
  "status": "NEEDS-ACTION",
  "calendar_id": "<calendar-name>"
}
```

### POST /tasks — create a task

```
POST /tasks
Content-Type: application/json

{
  "summary": "Write report",
  "description": "",
  "due": "2026-09-05T17:00:00",
  "status": "",
  "calendar_id": "<optional>"
}
```

Returns `201` with the created task.  `summary` is required;
`description`, `dtstart`, `due`, `status`, and `calendar_id` are
optional.

### PUT /tasks/{uid} — update a task

```
PUT /tasks/<uid>
Content-Type: application/json

{
  "summary": "...",
  "description": "...",
  "due": "2026-09-05T17:00:00",
  "status": "...",
  "calendar_id": "<optional>"
}
```

Replaces the task identified by `uid` and returns the updated task.

### DELETE /tasks/{uid} — delete a task

```
DELETE /tasks/<uid>?calendar_id=<optional>
```

Deletes the task (idempotent).  Returns `204` with no body.

---

## Contacts

### GET /contacts — list contacts

```
GET /contacts?addressbook_id=<optional>
```

Returns a JSON array of contact objects:

```json
{
  "uid": "<unique id>",
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "phone": "",
  "address": "",
  "addressbook_id": "<addressbook-name>"
}
```

### POST /contacts — create a contact

```
POST /contacts
Content-Type: application/json

{
  "full_name": "Ada Lovelace",
  "email": "ada@example.com",
  "phone": "",
  "address": "",
  "addressbook_id": "<optional>"
}
```

Returns `201` with the created contact.  `full_name` is required;
`email`, `phone`, `address`, and `addressbook_id` are optional.

### PUT /contacts/{uid} — update a contact

```
PUT /contacts/<uid>
Content-Type: application/json

{
  "full_name": "...",
  "email": "...",
  "phone": "...",
  "address": "...",
  "addressbook_id": "<optional>"
}
```

Replaces the contact identified by `uid` and returns the updated contact.

### DELETE /contacts/{uid} — delete a contact

```
DELETE /contacts/<uid>?addressbook_id=<optional>
```

Deletes the contact (idempotent).  Returns `204` with no body.

---

## Configuration surface

The component also serves its standard schema-driven settings surface:

| Endpoint | Description |
| -------- | ----------- |
| `GET /settings` | HTML settings panel (human UI). |
| `GET /config` | Stored config (secrets masked), JSON Schema, and current version. |
| `PUT /config` | Apply a partial config update; validates against the Settings model. |
| `GET /config/versions` | List recorded config versions, newest first. |
| `POST /config/rollback` | Restore an earlier config version as a new version. |

---

## Safety rules

1. **Mutations are confirmation-gated.** The `POST`, `PUT`, and
   `DELETE` endpoints above create, modify, or permanently remove live
   calendar data.  Before calling any of them, clearly state the change
   you intend to make (what object, what new fields) and obtain the
   user's confirmation in-conversation.

2. **Read before writing.** Prefer `GET /events`, `GET /tasks`, and
   `GET /contacts` to inspect the current data before creating or
   updating, so your writes are informed by what is actually stored.

3. **Deletes are irreversible.** For a `DELETE`, summarize exactly which
   object(s) will be removed and obtain explicit user confirmation.
"""


@router.get("/chat-skill", response_class=PlainTextResponse)
def chat_skill() -> PlainTextResponse:
    """Return the chat-agent component skill as a SKILL.md document.

    The response is ``text/markdown`` with YAML frontmatter so the
    chat agent can consume it as a standard skill file.
    """
    return PlainTextResponse(_CHAT_SKILL_TEXT, media_type="text/markdown")
