# robotsix-calendar-agent

In-process agent managing a Radicale CalDAV/CardDAV calendar and contacts.

The agent receives natural-language instructions, parses intent through
`robotsix-llmio`, and executes operations against a Radicale server.
No CLI, no web UI, no separate HTTP API — in-process only.

This repo follows the [robotsix stack standards](https://github.com/damien-robotsix/robotsix-standards).

## Status

![coverage](https://raw.githubusercontent.com/damien-robotsix/robotsix-calendar-agent/python-coverage-comment-action-data/badge.svg)

Early scaffold — under active development.

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
