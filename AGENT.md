# robotsix-calendar-agent — agent guidance

This repo follows the [robotsix stack standards](https://github.com/damien-robotsix/robotsix-standards).

## Scope & design

**Stateless agent** that brokers natural-language calendar/contact
instructions to a Radicale CalDAV/CardDAV server. Entry points:

| Entry point | Module | Description |
|---|---|---|
| Long-lived in-process service | `entrypoint.main` | Blocks until SIGTERM/SIGINT |
| In-process agent | `agent.CalendarAgent` | Constructs its own in-process `Agent` (used in tests / single-process mode) |

**No local data persistence** — there is no `data_dir_audit` and no
filesystem state. All state lives in the Radicale server.

**LLM operations always go through `robotsix_llmio`** — never call
provider SDKs directly. Intent parsing (`intent_parser.IntentParser`)
uses llmio with the `openrouter` provider extra. Tracing
requires the `tracing` extra (see Tracing below).

## Configuration conventions

All configuration lives in a single JSON config file
(`config/config.json`, overridable via `ROBOTSIX_CONFIG_FILE`) loaded
via **`robotsix_config.load_config(Settings)`** from
`src/robotsix_calendar_agent/settings/__init__.py`. Every field is documented
in `docs/configuration.md` with its type, default, and description.

**Rule:** When you add, remove, or change a `Settings` field in
`settings/__init__.py`, update `docs/configuration.md` and regenerate
`config/config.schema.json` in the same change. The
`config-schema-drift` CI job enforces that the committed schema stays
in sync with the model — it compares `config_schema_json(Settings)`
against the file and blocks merges that drift.

**Settings loaded at import/construction time** — `Settings()` is
instantiated inside `CalendarAgent.__init__` and `main()`, not at module
level. Tests use the `clean_env` autouse fixture (`tests/conftest.py`)
to prevent env-var leakage.

## Testing conventions

**Tests never touch the network.** Every external dependency is mocked:

| Dependency | Mock seam | How tests inject it |
|---|---|---|
| CalDAV library (`caldav`) | `sys.modules["caldav"]` | `tests/caldav_client/test_caldav_client.py` — `reset_mock_caldav` autouse fixture swaps in a `MagicMock` |
| LLM (`robotsix_llmio`) | `unittest.mock.patch` on `IntentParser` | `tests/conftest.py` — `calendar_agent` fixture patches `IntentParser` with `autospec=True` |
**Test layout mirrors source modules** — one test directory per source
module under `tests/` (e.g. `tests/agent/`, `tests/caldav_client/`).
Shared fixtures live in `tests/conftest.py`.

**Integration test**: `tests/caldav_client/test_caldav_integration.py`
uses a session-scoped `caldav_client` fixture from
`tests/caldav_client/caldav_test_server.py`. This fixture builds an
in-process wsgiref server wrapping ``radicale.app.Application`` on an
ephemeral port with a daemon thread — a real ``caldav.DAVClient``
pointed at an in-process Radicale. The CI integration job runs these
tests unconditionally and does not depend on a pre-provisioned Radicale
server or docker-compose.

## Tracing

Langfuse tracing is initialised at **module level** on `CalendarAgent`
import (`src/robotsix_calendar_agent/agent/__init__.py`):

```python
from robotsix_llmio.core import setup_langfuse_tracing

setup_langfuse_tracing()
```

This means importing `CalendarAgent` (or any module that imports it)
activates OpenTelemetry/OTLP export. The `robotsix-llmio[tracing]`
extra provides the required OTLP dependencies.

Two periodic workflows operate on tracing data:

- **`trace_review`** — surfaces anomalous traces for human review (repo-specific, see `.robotsix-mill/periodic/trace_review.yaml`).
- **`langfuse_cleanup`** — prunes stale trace sessions (framework-level; does not require a per-repo presence file).

Both are active and must not be disabled without coordination.

## Module layout

```
src/robotsix_calendar_agent/
├── __init__.py
├── agent/                     # CalendarAgent — wires everything together
│   ├── __init__.py             # CalendarAgent class, re-exports
│   ├── _dispatch.py            # dispatch table & handler functions
│   └── _reply.py               # reply rendering & formatting
├── caldav_client/              # typed CalDAV/CardDAV wrapper with retry logic via robotsix-http
│   ├── __init__.py
│   ├── _shared.py              # shared helpers
│   ├── calendar_ops.py         # calendar operations
│   ├── contact_ops.py          # contact operations
│   ├── exceptions.py           # CalDAV exception types
│   └── task_ops.py             # task (VTODO) operations
├── entrypoint/                 # main() — long-lived in-process service
│   ├── __init__.py
│   └── __main__.py
├── healthcheck/               # Docker HEALTHCHECK probe
│   └── __init__.py
├── intent_parser/
│   └── __init__.py             # IntentParser — llmio-based NL → ParsedIntent
├── py.typed                    # PEP 561 marker
└── settings/                   # BaseModel — loaded via robotsix_config.load_config from config.json
    └── __init__.py
```

> **Rule:** When adding a module-level import from an internal module to any file under `src/robotsix_calendar_agent/`, ensure the imported module appears in that file's `dependencies` list in `docs/modules.yaml`. Module-level `from .<module> import (...)` statements always require a corresponding `dependencies` entry — this is enforced by the periodic `module_curator` agent and violations will be flagged as draft tickets.

**Rationale:** Tickets such as `20260710T195032Z-...` (added `caldav_client` to `init.dependencies` after `__init__.py` imported `caldav_client.exceptions` at module level) and prior corrections `#255` and `#275` demonstrate that this convention is not obvious and has caused repeated drift in `docs/modules.yaml`.

**Provenance:** proposed by retrospect from 20260710T195032Z-docs-modules-yaml-init-depends-on-missin-7e16

## Dependencies


- **`robotsix-llmio[openrouter,tracing]`** — LLM intent parsing + Langfuse OTLP export
- **`caldav`** — CalDAV/CardDAV client library
- **`pydantic` / `robotsix-config`** — configuration & data models
- **`robotsix-http`** — HTTP client with retry logic
## Periodic workflows

This repo is targeted by **16 periodic agent workflows** (second-highest
in the fleet), plus one framework-level workflow (`langfuse_cleanup`) that
requires no per-repo stub. Key ones referenced above:

- `trace_review` — surfaces anomalous traces

When making changes, consider whether any periodic workflow's
expectations would be violated (e.g. changing a `Settings` field
without updating `config/config.schema.json` will cause the
`config-schema-drift` CI job to fail).
