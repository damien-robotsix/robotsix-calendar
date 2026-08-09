# Managing Calendar Events

This tutorial covers the four calendar-event operations —
**create**, **list**, **update**, and **delete** — using the
CalDAV client and intent parser directly.

We assume you've completed [Your First Agent](first-agent.md) and have
`config/config.json` configured with your Radicale credentials.

---

## Setup

Save this as `manage_events.py`:

```python
from robotsix_calendar_agent import CalendarAgent

agent = CalendarAgent()
```

We'll add each operation to the bottom of this script.  When you're done,
the `with agent:` context manager handles cleanup automatically.

---

## 1. Create an event

```python
from robotsix_calendar_agent.caldav_client import CalendarEvent

event = CalendarEvent(
    summary="Dentist appointment",
    dtstart="2026-06-09T15:00:00",
    dtend="2026-06-09T16:00:00",
)
created = agent._caldav.create_event(event)
uid = created.uid
print(f"Created: {created.summary} — uid={uid}")
```

---

## 2. List events

```python
events = agent._caldav.list_events(
    start="2026-06-01",
    end="2026-06-30",
)
print(f"Found {len(events)} event(s):")
for ev in events:
    print(f"  {ev.uid}  {ev.summary}  {ev.dtstart}")
```

---

## 3. Update an event

Use the `uid` from step 1:

```python
updated_event = CalendarEvent(
    summary="Dentist appointment (rescheduled)",
    dtstart="2026-06-09T16:00:00",
    dtend="2026-06-09T17:00:00",
)
result = agent._caldav.update_event(uid, updated_event)
print(f"Updated: {result.uid} — new start: {result.dtstart}")
```

---

## 4. Delete an event

```python
agent._caldav.delete_event(uid=uid)
print("Deleted.")
```

---

## Natural-language intent parsing

The agent also bundles an LLM-based intent parser that converts
free-form instructions into structured operations:

```python
parser = IntentParser()
parsed = parser.parse("add a dentist appointment next Tuesday at 3pm")
# parsed.operation → "create_event"
# parsed.params → {"summary": "Dentist appointment", "dtstart": "...", ...}
```

---

## Contacts too

The same pattern works for contacts — use `agent._caldav.create_contact`,
`list_contacts`, `update_contact`, and `delete_contact`.

---

## Next steps

- [Configuration](../../configuration.md) — complete config-file
  reference.
