# Configuration

All configuration is loaded from a single JSON config file
(`config/config.json` by default, overridable via the
`ROBOTSIX_CONFIG_FILE` environment variable) using
:func:`robotsix_config.load_config`. The settings model lives at
`src/robotsix_calendar_agent/settings/__init__.py`.

## Config file

::: robotsix_calendar_agent.settings

### Schema

A JSON Schema (`config/config.schema.json`) is committed alongside the
config file and kept in sync by the `config-schema-drift` CI check.
When you change `Settings` fields, regenerate the schema:

```bash
python -c "
from robotsix_config import config_schema_json
from robotsix_calendar_agent.settings import Settings
print(config_schema_json(Settings), end='')
" > config/config.schema.json
```

!!! note "Component agent removed"
    The component-agent management package has been removed.  See
    [`reference/component_agent.md`](reference/component_agent.md) for details
    on the removed component-agent responder and its replacement plan.
