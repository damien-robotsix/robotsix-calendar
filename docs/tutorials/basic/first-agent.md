# Your First Agent

This tutorial walks you through installing the agent, configuring your
Radicale credentials, and sending your first natural-language instruction.

**Prerequisites:** Python 3.14+, a running
[Radicale](https://radicale.org/) CalDAV server, and `uv` (the Python
package manager used throughout these docs).

---

## 1. Install

Clone the repository and install dependencies:

```bash
git clone https://github.com/damien-robotsix/robotsix-calendar-agent.git
cd robotsix-calendar-agent
uv sync
```

---

## 2. Configure Radicale access

The agent reads credentials from `config/config.json`.  Edit (or create)
that file with your Radicale server details:

```json
{
  "RADICALE_URL": "https://radicale.example.com",
  "RADICALE_USERNAME": "your-username",
  "RADICALE_PASSWORD": "your-password"
}
```

The config file path can be customised via the `ROBOTSIX_CONFIG_FILE`
environment variable.  For a full reference of every supported setting, see
[Configuration](../../configuration.md).

!!! tip "No Radicale server handy?"
    The project's test suite includes a CalDAV test server fixture
    (``tests/caldav_client/caldav_test_server.py``) that runs an
    ephemeral Radicale server entirely in-process via ``wsgiref`` —
    no container or docker-compose needed.  The fixture manages the
    server lifecycle automatically and tears down after the test
    session.

---

## 3. Write a minimal script

Create `hello_calendar.py`:

```python
from robotsix_calendar_agent import CalendarAgent

# -- instantiate the calendar agent -------------------------------------
agent = CalendarAgent()

# -- list calendars -----------------------------------------------------
with agent:
    calendars = agent._caldav.list_calendars()
    print("Your calendars:", calendars)
```

Run it:

```bash
uv run python hello_calendar.py
```

---

## 4. What just happened?

1. **Direct API** — the calendar agent runs in-process with no broker
   transport.  The CalDAV client and intent parser are accessed
   directly through the agent instance.

2. **`with agent:`** — the context manager provides a clean
   entry/exit scope for the agent.  The CalDAV client and intent
   parser remain accessible as attributes outside the block as well.

3. **CalDAV client** — `agent._caldav` provides typed methods for
   calendar, contact, and task operations against your Radicale server.

---

## 5. Next steps

- [Managing Calendar Events](manage-events.md) — create, update, and delete
  events.
- [Configuration](../../configuration.md) — complete configuration reference.
