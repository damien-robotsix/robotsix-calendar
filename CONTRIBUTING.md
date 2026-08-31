# Contributing to robotsix-calendar

Thanks for your interest in contributing! This document covers the
development setup and the conventions this repository follows.

## Development setup

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency and
environment management, and targets Python 3.14+.

```bash
git clone https://github.com/damien-robotsix/robotsix-calendar.git
cd robotsix-calendar
uv sync
```

The lockfile (`uv.lock`) is committed to the repository, and CI installs
dependencies with `uv sync --frozen`. When you change dependencies in
`pyproject.toml`, regenerate the lockfile with `uv lock` and commit the
result. **Never hand-edit `uv.lock`.**

**Supply-chain timing defense:** The project configures
[`exclude-newer`](https://docs.astral.sh/uv/reference/settings/#exclude-newer)
in `pyproject.toml` (`[tool.uv]` section), which prevents `uv lock`/`uv sync`
from resolving packages published within the last 7 days. This protects
against malicious package uploads during the window before CVEs are
published. If you need to temporarily override this (e.g. when testing a
just-published dependency), pass `--no-exclude-newer` to `uv lock` or
`uv sync`.

In CI, [`UV_MALWARE_CHECK=1`](https://docs.astral.sh/uv/concepts/projects/sync/#malware-checks)
is automatically set on all `uv` invocations (via the `setup-uv` composite
action), checking every dependency against the OpenSSF malicious-packages
database before code runs.

Note that this repository is **not** stdlib-only — it requires runtime
dependencies (`robotsix-llmio`, `caldav`) declared
in `pyproject.toml`.

## Checks

Run the full set of checks locally before opening a pull request.
Use `make` (run `make help` for all available targets):

```bash
make lint          # lint and format check
make typecheck     # static type checking (strict)
make test          # fast tests (non-integration)
make coverage      # run tests with coverage report (HTML + terminal)
make coverage-view # same, then open the HTML report in a browser
make all           # run all checks
```

`make format` rewrites files to the canonical format.

## Branches and pull requests

- Create a feature branch off `main` for your change.
- Keep changes focused and accompanied by tests where applicable.
- Ensure all checks above pass before requesting review.
- Open a pull request against `main`; CI runs the same checks.
