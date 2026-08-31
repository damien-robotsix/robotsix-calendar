# robotsix-calendar

An in-process agent that manages a Radicale server's calendars (CalDAV) and
contacts (CardDAV) — full read-write including delete.

## Architecture

```
Caller → CalendarAgent → IntentParser (llmio)
                       → CalDavClient (caldav) → Radicale
```

1. The caller sends a natural-language instruction (or a structured
   ``add_to_calendar`` payload) to the agent.
2. `CalendarAgent` passes NL instructions to `IntentParser`, which uses
   `robotsix-llmio` to classify them into one of 13 operations and extract
   structured parameters.
3. The parsed intent is dispatched to `CalDavClient`, which wraps the
   `caldav` library to perform CRUD operations against the Radicale server.
4. The result is returned to the caller.

## Getting started

### 1. Configure Radicale access

Edit (or create) `config/config.json` with your Radicale server details:

```json
{
  "radicale_url": "https://radicale.example.com",
  "radicale_username": "your-username",
  "radicale_password": "your-password"
}
```

The config file path can be customised via the `ROBOTSIX_CONFIG_FILE`
environment variable.  See [Configuration](configuration.md) for the full
config-file reference.

### 2. Install dependencies

```bash
uv sync
```

### 3. Start the agent

```python
from robotsix_calendar import CalendarAgent

agent = CalendarAgent()
with agent:
    # calendar operations go here
    pass
```

### 4. Use the agent directly

The agent wires together an :class:`IntentParser` and
:class:`CalDavClient`.  Use the public :meth:`CalendarAgent.run` method
to parse a natural-language instruction and dispatch it in one step:

```python
from robotsix_calendar import CalendarAgent

agent = CalendarAgent()

# Parse a natural-language instruction and dispatch it end-to-end
with agent:
    result = agent.run("create event Team Lunch tomorrow at noon")
    print(result)
```

`run()` returns whatever the dispatched CalDAV operation produces.  If
you need lower-level access, the bundled `IntentParser` and
`CalDavClient` remain available as `agent._parser` and `agent._caldav`:

```python
from robotsix_calendar import CalendarAgent

agent = CalendarAgent()

with agent:
    parsed = agent._parser.parse("create event Team Lunch tomorrow at noon")
    result = agent._dispatch(parsed)
    print(result)

with agent:
    calendars = agent._caldav.list_calendars()
    print(calendars)
```

## Deployment

The agent runs in-process.  Start it and work with the CalDAV client
and intent parser directly:

```python
from robotsix_calendar import CalendarAgent

agent = CalendarAgent()
with agent:
    # calendar operations go here
    pass
```

## Operations reference

| Operation | Example instruction | Key params |
|---|---|---|
| `list_calendars` | "what calendars do I have" | (none) |
| `list_events` | "list events this week" | `start`, `end` (ISO 8601) |
| `create_event` | "add a dentist appointment next Tuesday at 3pm" | `summary`, `dtstart`, `dtend` |
| `update_event` | "reschedule the dentist to 4pm" | `uid`, updated fields |
| `delete_event` | "cancel the dentist appointment" | `uid` |
| `list_tasks` | "show me my pending tasks" | `calendar_id?` |
| `create_task` | "add task buy groceries" | `summary`, `due?`, `status?` |
| `update_task` | "mark buy groceries as done" | `uid`, updated fields |
| `delete_task` | "remove buy groceries from tasks" | `uid` |
| `list_contacts` | "show all contacts" | (none) |
| `create_contact` | "add John Doe, john@example.com" | `full_name`, `email`, `phone` |
| `update_contact` | "change John's email to john.doe@example.com" | `uid`, updated fields |
| `delete_contact` | "remove John Doe from contacts" | `uid` |

## Configuration reference

See [Configuration](configuration.md) for the canonical config-file
reference.  All settings — including the three required Radicale
credentials — live in `config/config.json`.

Four additional optional keys (`radicale_default_calendar`, `caldav_timeout`,
`log_level`, `json_logs`) provide sensible defaults.  Copy
`config/config.example.json` to `config/config.json` as a starting template.


### Constructor options (`CalendarAgent`)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `agent_id` | `str` | `"calendar"` | Agent identifier |

### Public method (`CalendarAgent`)

| Method | Signature | Description |
|---|---|---|
| `run` | `run(text: str) -> Any` | Parse a natural-language calendar/contact instruction and dispatch it to the appropriate CalDAV operation. Raises `IntentParseError` on parse failure or `AgentLogicError` for unknown operations. |

