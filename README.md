# robotsix-calendar

In-process agent managing a Radicale CalDAV/CardDAV calendar and contacts.

The agent receives natural-language instructions, parses intent through
`robotsix-llmio`, and executes operations against a Radicale server.
No CLI, no web UI, no separate HTTP API — in-process only.

This repo follows the [robotsix stack standards](https://github.com/damien-robotsix/robotsix-standards).

## Status

![coverage](https://raw.githubusercontent.com/damien-robotsix/robotsix-calendar/python-coverage-comment-action-data/badge.svg)

Early scaffold — under active development.

## Getting Started

### Prerequisites

- Python 3.14+
- [`uv`](https://docs.astral.sh/uv/)
- A Radicale CalDAV/CardDAV server running locally or otherwise accessible

### Installation & Setup

```bash
git clone https://github.com/damien-robotsix/robotsix-calendar.git
cd robotsix-calendar
uv sync
```

### Quick Configuration

Copy the template at `config/config.example.json` to `config/config.json`
(or point `ROBOTSIX_CONFIG_FILE` at your own path) and fill in your
Radicale and OpenRouter credentials:

```json
{
  "radicale_url": "http://localhost:5232/",
  "radicale_username": "user",
  "radicale_password": "pass",
  "openrouter": { "keys": { "robotsix-calendar": "sk-or-..." } },
  "log_level": "INFO"
}
```

See [Configuration](docs/configuration.md) for every available setting.

### First Agent Call

```python
from robotsix_calendar.agent import CalendarAgent

with CalendarAgent() as agent:
    result = agent.run("Create an event tomorrow at 2pm called 'Team Meeting'")
    print(result)
```

### Next Steps

- See the [tutorials](docs/tutorials/basic/) for full CRUD examples.
- See [Configuration](docs/configuration.md) for all settings.
- See [Error Handling](docs/error-handling.md) for exception handling.

## Development

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency
management. The lockfile (`uv.lock`) is committed; CI installs with
`uv sync --frozen`.

```bash
uv sync
```

### Running checks

Use `make` (run `make help` for all targets):

```bash
make lint          # lint and format check
make typecheck     # static type checking (strict)
make test          # fast tests (non-integration)
make coverage      # run tests with coverage report (HTML + terminal)
make coverage-view # same, then open the HTML report in a browser
make all           # run all checks (default)
```

## Configuration

The agent reads credentials from `config/config.json` (customisable via
the `ROBOTSIX_CONFIG_FILE` environment variable).  See
[Configuration](docs/configuration.md) for all settings and the config-file
reference.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and
contribution guidelines. Project documentation lives under `docs/`.
