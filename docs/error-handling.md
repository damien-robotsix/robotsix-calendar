# Error Handling

Every CalDAV/CardDAV operation exposed by `CalDavClient` can fail —
because the resource does not exist, the server rejects the
credentials, another client modified the resource first, or the
network is unavailable. This page documents the exception hierarchy
those operations raise, how to catch and recover from each error, and
which retry behaviour is already handled for you.

## Exception hierarchy

All operational errors derive from a single base class,
`CalendarError`. Each subclass carries a stable machine-readable
`code` string (surfaced in the HTTP API as the `code` field of the
JSON problem response) and maps to a specific HTTP status when raised
through the REST API.

| Exception | `code` | HTTP status | Raised when |
|---|---|---|---|
| `NotFoundError` | `not_found` | 404 | calendar / event / contact / task not found |
| `AuthError` | `auth_failed` | 401 | Radicale authentication or authorization failure |
| `RateLimitError` | `rate_limited` | 429 | server rate limit (HTTP 429) |
| `ConflictError` | `conflict` | 409 | ETag mismatch (concurrent modification) |
| `CalDAVError` | `caldav_error` | 502 | any other CalDAV protocol / transport error (catch-all) |
| `AgentLogicError` | `agent_logic_error` | 400 | unknown operation or missing required parameter |

All six classes share the `CalendarError` base, so
`except CalendarError:` catches every operational error at once.

### `IntentParseError` is *not* a `CalendarError`

`IntentParseError` is raised only by the natural-language intent
parser (`IntentParser.parse`, and therefore `CalendarAgent.run()`)
when the LLM cannot turn an instruction into a structured intent. It
inherits directly from the built-in `Exception` — it is **not** a
`CalendarError` subclass, does not carry a `code`, and is not mapped
to an HTTP status by the CalDAV error handler. Catch it separately:

```python
from robotsix_calendar.intent_parser import IntentParseError
```

## Retry semantics

The `CalDavClient` operations are wrapped with retry logic before any
error mapping happens:

- **Transient network errors** — connection refused / reset, timeouts,
  DNS failures, broken pipes, and EOF — are retried automatically up
  to **3 times with exponential backoff**. Only if every retry fails
  is the error surfaced (mapped to `CalDAVError`).
- **`RateLimitError` is _not_ auto-retried.** A server `429` maps
  straight to `RateLimitError` and propagates to the caller. If you
  want retry-on-429 behaviour (e.g. honouring `Retry-After` with a
  backoff), you must implement it yourself — see
  [Recovery guidance](#recovery-guidance) below.

Because transient failures are already retried for you, a
`CalDAVError` that reaches your code represents a persistent problem,
not a momentary blip.

## Catching and handling errors

Import the exception classes from the `caldav_client` package (they
are all part of its public `__all__`):

```python
from robotsix_calendar.caldav_client import (
    CalDavClient,
    CalendarError,
    NotFoundError,
    AuthError,
    RateLimitError,
    ConflictError,
    CalDAVError,
)
```

### Catch a specific error type

```python
try:
    event = client.update_event(uid, updated_event)
except NotFoundError:
    print("That event no longer exists.")
```

### Catch the base class and inspect the code

Every `CalendarError` exposes two public attributes: `code` (the
stable string from the table above) and `message` (the human-readable
description, also returned by `str(e)`):

```python
try:
    client.create_event(event)
except CalendarError as e:
    # e.code   -> e.g. "conflict", "auth_failed", "caldav_error"
    # str(e)   -> the human-readable message (same as e.message)
    print(f"Operation failed [{e.code}]: {e}")
```

> The `code` string is the same value the REST API returns in the
> `code` field of its JSON error responses, so you can branch on it
> consistently across the Python and HTTP surfaces. (The class-level
> `_code` attribute is private — always read the public `code`
> attribute instead.)

## Which operations raise what

Every `CalDavClient` operation **except `health()`** is wrapped by the
retry-and-map decorator, so each can surface `AuthError`,
`RateLimitError`, or the catch-all `CalDAVError` depending on how the
server responds. The table below highlights the additional,
operation-specific errors verified against the client source:

| Operation | Notable exceptions |
|---|---|
| `list_calendars()` | `AuthError`, `RateLimitError`, `CalDAVError` |
| `health()` | *none* — returns a `{"connected": bool, ...}` status dict; probe failures are caught internally rather than raised |
| `list_events()` | `AuthError`, `RateLimitError`, `CalDAVError` |
| `create_event()` | `ConflictError`, `AuthError`, `RateLimitError`, `CalDAVError` |
| `update_event()` | `NotFoundError` (missing UID), `ConflictError`, `AuthError`, `RateLimitError`, `CalDAVError` |
| `delete_event()` | `AuthError`, `RateLimitError`, `CalDAVError` — **idempotent**: a missing UID returns `None`, it does *not* raise `NotFoundError` |
| `list_contacts()` | `AuthError`, `RateLimitError`, `CalDAVError` |
| `create_contact()` | `ConflictError`, `AuthError`, `RateLimitError`, `CalDAVError` |
| `update_contact()` | `NotFoundError` (missing UID), `ConflictError`, `AuthError`, `RateLimitError`, `CalDAVError` |
| `delete_contact()` | `AuthError`, `RateLimitError`, `CalDAVError` — **idempotent**: a missing UID returns `None` |
| `list_tasks()` | `AuthError`, `RateLimitError`, `CalDAVError` |
| `create_task()` | `ConflictError`, `AuthError`, `RateLimitError`, `CalDAVError` |
| `update_task()` | `NotFoundError` (missing UID), `ConflictError`, `AuthError`, `RateLimitError`, `CalDAVError` |
| `delete_task()` | `AuthError`, `RateLimitError`, `CalDAVError` — **idempotent**: a missing UID returns `None` |

The three `update_*` operations raise `NotFoundError` explicitly when
the target UID cannot be located. The three `delete_*` operations are
idempotent by design: deleting an already-absent resource is a no-op
that returns `None`.

## Recovery guidance

- **`NotFoundError`** — the resource is gone. For deletes this is
  already treated as success (idempotent). For reads / updates, surface
  a "not found" result to the user or fall back to creating the
  resource.
- **`ConflictError`** — another client modified the resource first
  (ETag mismatch). Re-read the current state, re-apply your change on
  top of it, then retry the write.
- **`RateLimitError`** — the server is throttling you. This is **not**
  retried automatically; wait (ideally with exponential backoff) and
  retry the call yourself, or shed load.
- **`AuthError`** — credentials are wrong or lack permission. This is
  not recoverable by retrying; surface it to the operator so the
  Radicale credentials can be corrected.
- **`CalDAVError`** — a persistent transport / protocol error that
  survived the automatic transient-retry logic. Log it and consider a
  circuit-breaker or a delayed retry; immediate re-attempts are
  unlikely to help.
- **`IntentParseError`** — the natural-language instruction could not
  be parsed. Ask the user to rephrase; there is nothing to retry
  server-side.
