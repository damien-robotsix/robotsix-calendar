# API

The FastAPI HTTP server exposes structured non-LLM CRUD endpoints for
calendar events, tasks, contacts, and calendar listing, plus a
robotsix-ui based UI access point (shared AppShell on every UI page) and
the standard schema-driven settings page and its config HTTP surface.

## UI access point

`GET /` redirects to the `/ui` landing page. The component serves five
robotsix-ui pages, each of which mounts the shared AppShell
(`mountAppShell` from `/static/robotsix-ui-vanilla.js`) with the primary
navigation Events `/ui/events`, Calendars `/ui/calendars`, Contacts
`/ui/contacts`, and Settings `/settings`:

| Endpoint | Description |
|---|---|
| `GET /` | Redirects to `/ui`. |
| `GET /ui` | Landing page with the app shell and links to the views. |
| `GET /ui/events` | Server-rendered page that fetches `GET /events` given a chosen calendar and date range, and renders the events grouped by day read-only (summary, start, end, location, description). |
| `GET /ui/calendars` | Server-rendered page that fetches `GET /calendars` and lists calendar names read-only, each linking to the events view. |
| `GET /ui/contacts` | Server-rendered page that fetches `GET /contacts` and renders contacts (name, email, phone, address, address book id). |
| `GET /settings` | App shell plus the schema-driven ConfigPanel. |

The `GET /events`, `GET /calendars`, and `GET /contacts` JSON API
endpoints are deliberately left untouched — the UI pages read them via
the distinct `/ui/*` paths, so the JSON API surface is unaffected.

Like every other component UI, the pages sit behind the central gateway —
the component itself adds no authentication.

## Chat skill surface

`GET /chat-skill` serves the component's **SKILL.md** document
(`text/markdown`, YAML frontmatter) that teaches the `robotsix-chat`
agent how to drive this API — calendars, events, tasks, contacts, the
error semantics, and the config surface. The central chat agent loads
the document through the component roster so it can read and manage a
user's calendar data directly.

## Settings page and config surface

The component serves a settings page at `/settings` that mounts the shared
`robotsix-ui` AppShell alongside the ConfigPanel (JSON-Schema driven,
React-free), so Settings is reachable from the primary navigation. The panel
is populated with the currently stored config read through the standard
config contract and persists edits through it — there is no separate local
config-file write path.

The config HTTP surface:

| Endpoint | Description |
|---|---|
| `GET /settings` | Renders the shared settings panel. |
| `GET /config` | Returns the stored config (secrets masked), the generated JSON Schema, and the current config version. |
| `PUT /config` | Applies a partial update via the standard versioned contract; returns the masked merged config. |
| `GET /config/versions` | Lists recorded config versions, newest first. |
| `POST /config/rollback` | Restores an earlier config version as a new version. |

Secret fields (e.g. `radicale_password`) are masked in responses per the
`Settings` schema annotations that the ConfigPanel honors, so secrets are
never returned to the panel and unsubmitted values are preserved on update.

Like every other component UI, the page sits behind the central gateway —
the component itself adds no authentication.

::: robotsix_calendar.api
