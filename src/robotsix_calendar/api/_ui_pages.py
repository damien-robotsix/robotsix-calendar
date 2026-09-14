"""HTML/JS page templates for the robotsix-ui UI access point.

Holds the full HTML pages and their embedded JavaScript as string
constants, plus the routes that serve them (``/``, ``/ui``,
``/ui/calendars``, ``/ui/events``, ``/ui/contacts``, ``/settings``).

Keeping the frontend templates in their own module — mirroring the
:mod:`robotsix_calendar.api._chat_skill` extraction — separates the
presentation layer from the CRUD/config handlers in
:mod:`robotsix_calendar.api` and keeps that module close to the repo's
size norm.  The routes here render read-only pages and depend on no
application state.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["UI"])

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


@router.get("/", response_class=RedirectResponse)
def root_page() -> RedirectResponse:
    """Redirect the root path to the /ui landing page."""
    return RedirectResponse(url="/ui", status_code=307)


@router.get("/ui", response_class=HTMLResponse)
def ui_landing_page() -> str:
    """Render the landing page with the shared app shell."""
    return _ui_page("robotsix-calendar", "/", _UI_LANDING_CONTENT)


@router.get("/ui/calendars", response_class=HTMLResponse)
def ui_calendars_page() -> str:
    """Render a read-only list of calendars fetched from GET /calendars."""
    return _ui_page("Calendars", "/ui/calendars", _CALENDARS_PAGE_CONTENT)


@router.get("/ui/events", response_class=HTMLResponse)
def ui_events_page() -> str:
    """Render a read-only event agenda fetched from GET /events."""
    return _ui_page("Events", "/ui/events", _EVENTS_PAGE_CONTENT)


@router.get("/ui/contacts", response_class=HTMLResponse)
def ui_contacts_page() -> str:
    """Render a read-only list of contacts fetched from GET /contacts."""
    return _ui_page("Contacts", "/ui/contacts", _CONTACTS_PAGE_CONTENT)


@router.get("/settings", response_class=HTMLResponse)
def settings_page() -> str:
    """Render the shared app shell plus the schema-driven settings panel."""
    return _ui_page("Settings", "/settings", _SETTINGS_PAGE_CONTENT)
