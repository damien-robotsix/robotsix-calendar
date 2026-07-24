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
  "radicale_url": "https://radicale.example.com",
  "radicale_username": "your-username",
  "radicale_password": "your-password"
}
```

The config file path can be customised via the `ROBOTSIX_CONFIG_FILE`
environment variable.  For a full reference of every supported setting, see
[Configuration](../../configuration.md).

!!! tip "No Radicale server handy?"
    The project's test suite includes a CalDAV test server fixture
    (``tests/caldav_client/caldav_test_server.py``)
    that spins up a local Radicale container via docker-compose.  You can
    point `radicale_url` at `http://localhost:5232` in your config after running it.

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

- [Managing Calendar Events](../../agent/tutorials/manage-events.md) — create, update, and delete
  events.
<<<<<<< HEAD
- [Configuration](../../configuration.md) — complete config-file
=======
- [Configuration](../../configuration.md) — complete configuration
>>>>>>> d3622ed (mill: Update README.md and docs/ after config migration from env vars to config.json)
  reference.
mplete config-file
  reference.
>>>>>>> d3622ed (mill: Update README.md and docs/ after config migration from env vars to config.json (20260722T205416Z-update-readme-md-and-docs-after-config-m-8f70))
  reference.
mplete config-file
  reference.
