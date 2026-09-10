"""FastAPI HTTP server exposing structured CRUD endpoints.

Provides non-LLM REST endpoints for calendar events, tasks, contacts,
and calendar listing.  The :class:`CalDavClient` instance is injected
via ``app.state.caldav_client`` (set by the entrypoint at startup).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from robotsix_config import (
    InvalidConfigError,
    apply_update,
    config_schema,
    current_version,
    mask_secrets,
    read_versions,
    resolve_config_path,
    rollback,
)

from ..caldav_client import CalDavClient
from ..caldav_client._shared import CalendarEvent, Contact, Task
from ..caldav_client.exceptions import (
    AuthError,
    CalDAVError,
    CalendarError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)
from ..settings import Settings
from ._chat_skill import router as _chat_skill_router

logger = logging.getLogger(__name__)

__all__ = ["app"]

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    """Body for creating or updating a calendar event."""

    summary: str
    description: str = ""
    location: str = ""
    dtstart: str
    dtend: str
    calendar_id: str = ""


class EventResponse(BaseModel):
    """Serialized calendar event."""

    uid: str
    summary: str
    description: str
    location: str
    dtstart: str
    dtend: str
    calendar_id: str


class TaskCreate(BaseModel):
    """Body for creating or updating a task."""

    summary: str
    description: str = ""
    dtstart: str = ""
    due: str = ""
    status: str = ""
    calendar_id: str = ""


class TaskResponse(BaseModel):
    """Serialized task."""

    uid: str
    summary: str
    description: str
    dtstart: str
    due: str
    status: str
    calendar_id: str


class ContactCreate(BaseModel):
    """Body for creating or updating a contact."""

    full_name: str
    email: str = ""
    phone: str = ""
    address: str = ""
    addressbook_id: str = ""


class ContactResponse(BaseModel):
    """Serialized contact."""

    uid: str
    full_name: str
    email: str
    phone: str
    address: str
    addressbook_id: str


class CalendarInfo(BaseModel):
    """Serialized calendar entry."""

    name: str


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Calendar Agent API")

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(_chat_skill_router)


# ---------------------------------------------------------------------------
# Dependency — CalDavClient from app.state
# ---------------------------------------------------------------------------


def _get_client(request: Request) -> CalDavClient:
    """Return the shared :class:`CalDavClient` stored on ``app.state``."""
    return request.app.state.caldav_client  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Exception handler — map CalendarError subclasses to HTTP status codes
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[type[CalendarError], int] = {
    NotFoundError: 404,
    AuthError: 401,
    ConflictError: 409,
    RateLimitError: 429,
    CalDAVError: 502,
}


@app.exception_handler(CalendarError)
async def _calendar_error_handler(request: Request, exc: CalendarError) -> JSONResponse:
    status = _STATUS_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status,
        content={"detail": exc.message, "code": exc.code},
    )


# ---------------------------------------------------------------------------
# Helpers — convert dataclass → Pydantic response model
# ---------------------------------------------------------------------------


def _event_to_response(event: CalendarEvent) -> EventResponse:
    return EventResponse(
        uid=event.uid,
        summary=event.summary,
        description=event.description,
        location=event.location,
        dtstart=event.dtstart,
        dtend=event.dtend,
        calendar_id=event.calendar_id,
    )


def _task_to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        uid=task.uid,
        summary=task.summary,
        description=task.description,
        dtstart=task.dtstart,
        due=task.due,
        status=task.status,
        calendar_id=task.calendar_id,
    )


def _contact_to_response(contact: Contact) -> ContactResponse:
    return ContactResponse(
        uid=contact.uid,
        full_name=contact.full_name,
        email=contact.email,
        phone=contact.phone,
        address=contact.address,
        addressbook_id=contact.addressbook_id,
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@app.get("/events", response_model=list[EventResponse])
def list_events(
    start: Annotated[str, Query(description="ISO 8601 start")],
    end: Annotated[str, Query(description="ISO 8601 end")],
    calendar_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> list[EventResponse]:
    """List events in the given date range."""
    events = client.list_events(start, end, calendar_id)
    return [_event_to_response(e) for e in events]


@app.post("/events", response_model=EventResponse, status_code=201)
def create_event(
    body: EventCreate,
    client: CalDavClient = Depends(_get_client),
) -> EventResponse:
    """Create a new calendar event."""
    event = CalendarEvent(
        summary=body.summary,
        description=body.description,
        location=body.location,
        dtstart=body.dtstart,
        dtend=body.dtend,
        calendar_id=body.calendar_id,
    )
    created = client.create_event(event, calendar_id=body.calendar_id)
    return _event_to_response(created)


@app.put("/events/{uid}", response_model=EventResponse)
def update_event(
    uid: str,
    body: EventCreate,
    client: CalDavClient = Depends(_get_client),
) -> EventResponse:
    """Update an existing calendar event."""
    event = CalendarEvent(
        summary=body.summary,
        description=body.description,
        location=body.location,
        dtstart=body.dtstart,
        dtend=body.dtend,
        calendar_id=body.calendar_id,
    )
    updated = client.update_event(uid, event, calendar_id=body.calendar_id)
    return _event_to_response(updated)


@app.delete("/events/{uid}", status_code=204)
def delete_event(
    uid: str,
    calendar_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> None:
    """Delete a calendar event (idempotent)."""
    client.delete_event(uid, calendar_id)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@app.get("/tasks", response_model=list[TaskResponse])
def list_tasks(
    calendar_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> list[TaskResponse]:
    """List all tasks."""
    tasks = client.list_tasks(calendar_id)
    return [_task_to_response(t) for t in tasks]


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    body: TaskCreate,
    client: CalDavClient = Depends(_get_client),
) -> TaskResponse:
    """Create a new task."""
    task = Task(
        summary=body.summary,
        description=body.description,
        dtstart=body.dtstart,
        due=body.due,
        status=body.status,
        calendar_id=body.calendar_id,
    )
    created = client.create_task(task, calendar_id=body.calendar_id)
    return _task_to_response(created)


@app.put("/tasks/{uid}", response_model=TaskResponse)
def update_task(
    uid: str,
    body: TaskCreate,
    client: CalDavClient = Depends(_get_client),
) -> TaskResponse:
    """Update an existing task."""
    task = Task(
        summary=body.summary,
        description=body.description,
        dtstart=body.dtstart,
        due=body.due,
        status=body.status,
        calendar_id=body.calendar_id,
    )
    updated = client.update_task(uid, task, calendar_id=body.calendar_id)
    return _task_to_response(updated)


@app.delete("/tasks/{uid}", status_code=204)
def delete_task(
    uid: str,
    calendar_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> None:
    """Delete a task (idempotent)."""
    client.delete_task(uid, calendar_id)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@app.get("/contacts", response_model=list[ContactResponse])
def list_contacts(
    addressbook_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> list[ContactResponse]:
    """List all contacts."""
    contacts = client.list_contacts(addressbook_id)
    return [_contact_to_response(c) for c in contacts]


@app.post("/contacts", response_model=ContactResponse, status_code=201)
def create_contact(
    body: ContactCreate,
    client: CalDavClient = Depends(_get_client),
) -> ContactResponse:
    """Create a new contact."""
    contact = Contact(
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        address=body.address,
        addressbook_id=body.addressbook_id,
    )
    created = client.create_contact(contact, addressbook_id=body.addressbook_id)
    return _contact_to_response(created)


@app.put("/contacts/{uid}", response_model=ContactResponse)
def update_contact(
    uid: str,
    body: ContactCreate,
    client: CalDavClient = Depends(_get_client),
) -> ContactResponse:
    """Update an existing contact."""
    contact = Contact(
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        address=body.address,
        addressbook_id=body.addressbook_id,
    )
    updated = client.update_contact(uid, contact, addressbook_id=body.addressbook_id)
    return _contact_to_response(updated)


@app.delete("/contacts/{uid}", status_code=204)
def delete_contact(
    uid: str,
    addressbook_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> None:
    """Delete a contact (idempotent)."""
    client.delete_contact(uid, addressbook_id)


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------


@app.get("/calendars", response_model=list[CalendarInfo])
def list_calendars(
    client: CalDavClient = Depends(_get_client),
) -> list[CalendarInfo]:
    """List all calendar names."""
    names = client.list_calendars()
    return [CalendarInfo(name=n) for n in names]


# ---------------------------------------------------------------------------
# Settings page + standard config surface (shared ConfigPanel)
# ---------------------------------------------------------------------------

_UI_NAV: tuple[tuple[str, str], ...] = (
    ("/ui/events", "Events"),
    ("/ui/calendars", "Calendars"),
    ("/ui/contacts", "Contacts"),
    ("/settings", "Settings"),
)


def _ui_page(page_title: str, active_href: str, content: str) -> str:
    """Render a robotsix-ui app-shell page with the shared primary nav.

    Every UI page mounts the shared ``mountAppShell`` from
    ``/static/robotsix-ui-vanilla.js`` with the standard three nav entries
    (Calendars, Contacts, Settings); ``active_href`` marks the current page.
    """
    nav_entries = []
    for href, label in _UI_NAV:
        active = "true" if href == active_href else "false"
        nav_entries.append(
            f'          {{ href: "{href}", label: "{label}", active: {active} }}'
        )
    nav = ",\n".join(nav_entries)
    return f"""\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{page_title}</title>
    <link rel="stylesheet" href="/static/robotsix-ui.css">
  </head>
  <body>
    <div id="app"></div>
{content}
    <script type="module">
      import {{ mountAppShell }} from "/static/robotsix-ui-vanilla.js";
      mountAppShell(document.getElementById("app"), {{
        brand: "Calendar",
        navItems: [
{nav}
        ],
        settingsHref: "/settings",
      }});
    </script>
  </body>
</html>
"""


_UI_LANDING_CONTENT = """\
    <main class="ui-page">
      <h1>robotsix-calendar</h1>
      <p>Manage your calendars and contacts from the navigation above.</p>
      <ul class="ui-links">
        <li><a href="/ui/calendars">Calendars</a></li>
        <li><a href="/ui/contacts">Contacts</a></li>
        <li><a href="/settings">Settings</a></li>
      </ul>
    </main>
"""

_CALENDARS_PAGE_CONTENT = """\
    <main class="ui-page">
      <h1>Calendars</h1>
      <p><a class="ui-link" href="/ui/events">View events</a></p>
      <ul id="calendar-list" class="ui-list"></ul>
    </main>
    <script type="module">
      function escapeHtml(value) {
        const node = document.createElement("span");
        node.textContent = String(value ?? "");
        return node.innerHTML;
      }
      function escapeAttr(value) {
        return escapeHtml(value).replace(/"/g, "&quot;");
      }

      async function loadCalendars() {
        const list = document.getElementById("calendar-list");
        try {
          const response = await fetch("/calendars");
          const calendars = await response.json();
          list.innerHTML = calendars.length
            ? calendars.map(
                (cal) =>
                  `<li class="ui-item">` +
                  `<a href="/ui/events?calendar=${encodeURIComponent(cal.name)}">` +
                  `${escapeHtml(cal.name)}</a></li>`,
              ).join("")
            : '<li class="ui-item">No calendars found.</li>';
        } catch (error) {
          const detail = escapeHtml(error.message);
          list.innerHTML =
            '<li class="ui-item">Failed to load calendars: ' + detail + '</li>';
        }
      }

      loadCalendars();
    </script>
"""

_EVENTS_PAGE_CONTENT = """\
    <main class="ui-page">
      <h1>Events</h1>
      <form id="event-form" class="ui-form">
        <label>Calendar
          <select id="event-calendar">
            <option value="">All calendars</option>
          </select>
        </label>
        <label>From
          <input type="date" id="event-start" required>
        </label>
        <label>To
          <input type="date" id="event-end" required>
        </label>
        <div class="ui-form-actions">
          <button type="button" id="event-prev">Previous month</button>
          <button type="button" id="event-next">Next month</button>
          <button type="submit" id="event-load">Load</button>
        </div>
      </form>
      <div id="event-list" class="ui-list"></div>
    </main>
    <script type="module">
      function escapeHtml(value) {
        const node = document.createElement("span");
        node.textContent = String(value ?? "");
        return node.innerHTML;
      }
      function escapeAttr(value) {
        return escapeHtml(value).replace(/"/g, "&quot;");
      }

      function formatDate(iso) {
        if (!iso) return "";
        const date = new Date(iso);
        return isNaN(date.getTime()) ? String(iso) : date.toLocaleString();
      }

      function fmtDay(date) {
        const mm = String(date.getMonth() + 1).padStart(2, "0");
        const dd = String(date.getDate()).padStart(2, "0");
        return date.getFullYear() + "-" + mm + "-" + dd;
      }

      const calendarSelect = document.getElementById("event-calendar");
      const startInput = document.getElementById("event-start");
      const endInput = document.getElementById("event-end");
      const form = document.getElementById("event-form");
      const prevBtn = document.getElementById("event-prev");
      const nextBtn = document.getElementById("event-next");
      const list = document.getElementById("event-list");

      // Range defaults to the current calendar month; prev/next shift by month.
      let monthOffset = 0;

      function monthRange(offset) {
        const now = new Date();
        const first = new Date(now.getFullYear(), now.getMonth() + offset, 1);
        const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
        return { start: fmtDay(first), end: fmtDay(last) };
      }

      // `doLoad` is false only for the initial render when a `calendar`
      // query param is present: the first fetch must wait for the
      // calendar dropdown to be populated so the preselect applies
      // (see loadCalendars + the startup calls at the bottom).
      function applyMonth(doLoad) {
        const range = monthRange(monthOffset);
        startInput.value = range.start;
        endInput.value = range.end;
        if (doLoad !== false) loadEvents();
      }

      function dayKey(iso) {
        return String(iso || "").slice(0, 10);
      }

      function eventCard(ev) {
        const description = ev.description
          ? '<p class="ui-note">' + escapeHtml(ev.description) + "</p>"
          : "";
        const location = ev.location
          ? '<p class="ui-note">Location: ' + escapeHtml(ev.location) + "</p>"
          : "";
        return (
          '<article class="ui-card">' +
          "<h3>" + escapeHtml(ev.summary) + "</h3>" +
          '<p class="ui-meta">' + escapeHtml(formatDate(ev.dtstart)) +
          " &rarr; " + escapeHtml(formatDate(ev.dtend)) + "</p>" +
          location +
          description +
          "</article>"
        );
      }

      function renderEvents(events) {
        const sorted = events.slice().sort(function (a, b) {
          return String(a.dtstart || "").localeCompare(String(b.dtstart || ""));
        });
        const byDay = new Map();
        for (const ev of sorted) {
          const key = dayKey(ev.dtstart) || "Other";
          if (!byDay.has(key)) byDay.set(key, []);
          byDay.get(key).push(ev);
        }
        let html = "";
        for (const [day, dayEvents] of byDay) {
          html += '<section class="ui-day"><h2>' + escapeHtml(day) + "</h2>";
          for (const ev of dayEvents) html += eventCard(ev);
          html += "</section>";
        }
        return html;
      }

      async function loadEvents() {
        const start = startInput.value;
        const end = endInput.value;
        if (!start || !end) {
          list.innerHTML =
            '<p class="ui-note">Please choose a from and to date.</p>';
          return;
        }
        const params = new URLSearchParams({ start: start, end: end });
        const calendarId = calendarSelect.value;
        if (calendarId) params.set("calendar_id", calendarId);
        try {
          const response = await fetch("/events?" + params.toString());
          if (!response.ok) {
            let detail = "HTTP " + response.status;
            try {
              const body = await response.json();
              if (body && body.detail) detail += ": " + body.detail;
            } catch (e) {
              // Non-JSON error body; keep the status detail.
            }
            throw new Error(detail);
          }
          const events = await response.json();
          if (!Array.isArray(events)) {
            throw new Error("Unexpected response from /events");
          }
          if (events.length === 0) {
            list.innerHTML =
              '<p class="ui-note">No events in this range.</p>';
            return;
          }
          list.innerHTML = renderEvents(events);
        } catch (error) {
          const detail = escapeHtml(error.message || "unknown error");
          list.innerHTML =
            '<p class="ui-error">Failed to load events: ' + detail + "</p>";
        }
      }

      async function loadCalendars() {
        const wanted = new URLSearchParams(window.location.search).get(
          "calendar",
        );
        try {
          const response = await fetch("/calendars");
          const calendars = await response.json();
          let options = '<option value="">All calendars</option>';
          for (const cal of calendars) {
            options +=
              '<option value="' + escapeAttr(cal.name) + '">' +
              escapeHtml(cal.name) + "</option>";
          }
          calendarSelect.innerHTML = options;
          if (wanted) {
            calendarSelect.value = wanted;
            // The dropdown is populated now, so the preselect applies to
            // the first fetch — load events with the selection in place.
            loadEvents();
          }
        } catch (error) {
          calendarSelect.insertAdjacentHTML(
            "beforeend",
            '<option value="">Calendars unavailable</option>',
          );
          // A preselect cannot be applied without the dropdown, but keep the
          // page functional when one was requested; otherwise applyMonth()
          // already fired the initial load with the default selection.
          if (wanted) loadEvents();
        }
      }

      form.addEventListener("submit", function (event) {
        event.preventDefault();
        loadEvents();
      });
      prevBtn.addEventListener("click", function () {
        monthOffset -= 1;
        applyMonth();
      });
      nextBtn.addEventListener("click", function () {
        monthOffset += 1;
        applyMonth();
      });

      // With a `calendar` query param, the initial fetch must wait for the
      // dropdown to be populated (loadCalendars fires loadEvents then); with
      // no param the default all-calendars selection is already correct, so
      // the events load immediately.
      const calendarParam = new URLSearchParams(window.location.search).get(
        "calendar",
      );
      loadCalendars();
      applyMonth(calendarParam ? false : true);
    </script>
"""

_CONTACTS_PAGE_CONTENT = """\
    <main class="ui-page">
      <h1>Contacts</h1>
      <table id="contacts-table" class="ui-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Phone</th>
            <th>Address</th>
            <th>Address Book</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </main>
    <script type="module">
      function escapeHtml(value) {
        const node = document.createElement("span");
        node.textContent = String(value ?? "");
        return node.innerHTML;
      }

      async function loadContacts() {
        const body = document.querySelector("#contacts-table tbody");
        try {
          const response = await fetch("/contacts");
          const contacts = await response.json();
          body.innerHTML = contacts.length
            ? contacts.map(
                (contact) =>
                  `<tr>
                    <td>${escapeHtml(contact.full_name)}</td>
                    <td>${escapeHtml(contact.email)}</td>
                    <td>${escapeHtml(contact.phone)}</td>
                    <td>${escapeHtml(contact.address)}</td>
                    <td>${escapeHtml(contact.addressbook_id)}</td>
                  </tr>`,
              ).join("")
            : '<tr><td colspan="5">No contacts found.</td></tr>';
        } catch (error) {
          const detail = escapeHtml(error.message);
          body.innerHTML = `<tr><td colspan="5">Load failed: ${detail}</td></tr>`;
        }
      }

      loadContacts();
    </script>
"""

_SETTINGS_PAGE_CONTENT = """\
    <main class="ui-page">
      <div id="settings"></div>
    </main>
    <script type="module">
      import { mountConfigPanel } from "/static/robotsix-ui-vanilla.js";
      mountConfigPanel(document.getElementById("settings"), { title: "Settings" });
    </script>
"""


def _read_stored_config() -> dict[str, Any]:
    """Return the raw config document from the standard config file.

    Deliberately does **not** round-trip through :class:`Settings` — the
    model would fill absent keys with schema defaults, and the panel must
    see exactly what is stored so it never posts defaults back over real
    values.
    """
    path = resolve_config_path()
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=500,
            detail=f"Config top level in {path} must be a JSON object",
        )
    return data


def _masked_config_response(config: dict[str, Any], version: int) -> dict[str, Any]:
    """Render the standard GET/PUT config envelope with secrets masked."""
    return {
        "config": mask_secrets(config, Settings),
        "schema": config_schema(Settings),
        "version": version,
    }


class ConfigRollbackRequest(BaseModel):
    """Body for restoring a previous config version."""

    version: int


@app.get("/", response_class=RedirectResponse)
def root_page() -> RedirectResponse:
    """Redirect the root path to the /ui landing page."""
    return RedirectResponse(url="/ui", status_code=307)


@app.get("/ui", response_class=HTMLResponse)
def ui_landing_page() -> str:
    """Render the landing page with the shared app shell."""
    return _ui_page("robotsix-calendar", "/", _UI_LANDING_CONTENT)


@app.get("/ui/calendars", response_class=HTMLResponse)
def ui_calendars_page() -> str:
    """Render a read-only list of calendars fetched from GET /calendars."""
    return _ui_page("Calendars", "/ui/calendars", _CALENDARS_PAGE_CONTENT)


@app.get("/ui/events", response_class=HTMLResponse)
def ui_events_page() -> str:
    """Render a read-only event agenda fetched from GET /events."""
    return _ui_page("Events", "/ui/events", _EVENTS_PAGE_CONTENT)


@app.get("/ui/contacts", response_class=HTMLResponse)
def ui_contacts_page() -> str:
    """Render a read-only list of contacts fetched from GET /contacts."""
    return _ui_page("Contacts", "/ui/contacts", _CONTACTS_PAGE_CONTENT)


@app.get("/settings", response_class=HTMLResponse)
def settings_page() -> str:
    """Render the shared app shell plus the schema-driven settings panel."""
    return _ui_page("Settings", "/settings", _SETTINGS_PAGE_CONTENT)


@app.get("/config")
def get_config() -> dict[str, Any]:
    """Return stored config (secrets masked), schema, and current version."""
    stored = _read_stored_config()
    return _masked_config_response(stored, current_version())


@app.put("/config")
def update_config(payload: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
    """Apply a partial config update via the standard versioned contract."""
    try:
        merged, _changed, version = apply_update(Settings, payload)
    except InvalidConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _masked_config_response(merged, version)


@app.get("/config/versions")
def get_config_versions() -> dict[str, Any]:
    """List recorded config versions, newest first."""
    versions = read_versions(include_data=False)
    return {"versions": list(reversed(versions))}


@app.post("/config/rollback")
def rollback_config(payload: ConfigRollbackRequest) -> dict[str, Any]:
    """Restore an earlier config version as a new version."""
    try:
        restored, _changed, version = rollback(Settings, payload.version)
    except InvalidConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _masked_config_response(restored, version)
