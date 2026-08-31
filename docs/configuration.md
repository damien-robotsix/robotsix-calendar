# Configuration

All configuration is loaded from a single JSON config file
(`config/config.json` by default, overridable via the
`ROBOTSIX_CONFIG_FILE` environment variable) using
:func:`robotsix_config.load_config`. The settings model lives at
`src/robotsix_calendar/settings/__init__.py`.

## Config file

::: robotsix_calendar.settings

### Schema

A JSON Schema (`config/config.schema.json`) is committed alongside the
config file and kept in sync by the `config-schema-drift` CI check.
When you change `Settings` fields, regenerate the schema:

```bash
python -c "
from robotsix_config import config_schema_json
from robotsix_calendar.settings import Settings
print(config_schema_json(Settings), end='')
" > config/config.schema.json
```

## Langfuse

The `langfuse` block provides Langfuse observability credentials as a
canonical block for the deployment engine.  It is optional — when
omitted (or set to ``null``), Langfuse tracing is not initialised.

```json
{
  "langfuse": {
    "host": "https://langfuse.example.com",
    "projects": {
      "robotsix-calendar": {
        "public_key": "pk-...",
        "secret_key": "sk-...",
        "project_id": ""
      }
    }
  }
}
```

The `projects` map uses the component alias as the key — currently
``robotsix-calendar``.  When set, the agent exports ``LANGFUSE_HOST``,
``LANGFUSE_PUBLIC_KEY``, and ``LANGFUSE_SECRET_KEY`` to the process
environment before calling ``setup_langfuse_tracing()``.

## OpenRouter

The `openrouter` block provides OpenRouter API keys as a canonical block
for the deployment engine.  It is optional — when omitted (or set to
``null``), the LLM provider falls back to the ``OPENROUTER_API_KEY``
environment variable.

```json
{
  "openrouter": {
    "keys": {
      "robotsix-calendar": "sk-or-..."
    }
  }
}
```

The `keys` map uses the same component alias as ``langfuse.projects``.
Currently the key is declared for future wiring (the
:class:`~robotsix_calendar.intent_parser.IntentParser` accepts
an ``api_key`` parameter for this purpose).

!!! note "Component agent removed"
    The component-agent management package has been removed.  See
    [`reference/component_agent.md`](reference/component_agent.md) for details
    on the removed component-agent responder and its replacement plan.
