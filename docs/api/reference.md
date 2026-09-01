# API

The FastAPI HTTP server exposes structured non-LLM CRUD endpoints for
calendar events, tasks, contacts, and calendar listing, plus a
robotsix-ui based UI access point (app shell + calendars/contacts
visualisation) and the standard schema-driven settings page and its
config HTTP surface.

## UI access point

`GET /` renders a robotsix-ui based page that mounts the shared
`robotsix-ui` app shell (`mountAppShell`) and visualises the user's
calendars and contacts by fetching the `GET /calendars` and
`GET /contacts` endpoints from the browser. Navigation links through to
the schema-driven settings page at `/settings`. Like every other
component UI, the page sits behind the central gateway — the component
itself adds no authentication.

## Chat skill surface

`GET /chat-skill` serves the component's **SKILL.md** document
(`text/markdown`, YAML frontmatter) that teaches the `robotsix-chat`
agent how to drive this API — calendars, events, tasks, contacts, the
error semantics, and the config surface. The central chat agent loads
the document through the component roster so it can read and manage a
user's calendar data directly.

## Settings page and config surface

The component serves a minimal settings page at `/settings` that embeds
the shared `robotsix-ui` ConfigPanel (JSON-Schema driven, React-free).
The panel is populated with the currently stored config read through the
standard config contract and persists edits through it — there is no
separate local config-file write path.

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
