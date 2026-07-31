## 0.0.0 (unreleased)


- Added dedicated unit tests for `agent/_dispatch.py` helpers (`tests/agent/test__dispatch.py`): 47 pure unit tests covering `_build_event`, `_build_task`, `_build_contact` default-value fallbacks, `_entity_op` create/update branching and UID validation, `_delete_entity_op` blank-UID and missing-UID edge cases, and all `_handle_*` functions.
- Remove stale `llm_model_config` references from README and docs index — the parameter
  was removed from `CalendarAgent.__init__` in PR #393.
- Remove dead `_intent_parser` field and `llm_model_config` parameter from `CalendarAgent.__init__`. The agent never invoked `IntentParser.parse()` — intents are pre-parsed by the caller. Also removes the inaccurate vulture whitelist entry that was masking this dead code.
- Add exception types (`AgentLogicError`, `AuthError`, `CalDAVError`, `CalendarError`, `ConflictError`, `NotFoundError`, `RateLimitError`) to top-level `__all__` so static analysis tools recognise them as intentional public API re-exports.
- Add missing `__all__` declarations to `healthcheck/`, `intent_parser/`, and `settings/` subpackage `__init__.py` files to prevent private symbols from leaking via wildcard imports.
- Split `agent/__init__.py` (462 lines) into three submodules: `_dispatch.py` (dispatch table and handlers), `_reply.py` (reply rendering), and a slimmer `__init__.py` (CalendarAgent class and re-exports).
- Add `create_task`, `update_task`, and `delete_task` CRUD methods to
  `_TaskOpsMixin`, with private helpers `_task_to_ical` and `_find_task_by_uid`.
  Fixes: use `save_todo` (not `save_event`) for VTODO persistence; use
  `get_todo_by_uid` for UID lookups; add conditional guards for optional
  DTSTART/DUE/STATUS fields in iCal serialization.
- Enable ruff rules `N` (pep8-naming), `ERA` (eradicate), and `PGH` (pygrep-hooks)
- Add `.python-version` file (3.14) for uv/pyenv version pinning.
- Fix AGENT.md `Periodic workflows` section: correct the count from 15 to 14
  (repo-level stubs), credit the framework-level `langfuse_cleanup` as the
  15th, and remove `config-schema-drift` from the periodic workflow examples
  (it is a CI workflow, not a periodic agent workflow).
- Fix stale `tenacity` references in AGENT.md: update caldav_client module description to "retry logic via robotsix-http" and remove removed `tenacity>=9.0` dependency entry; add `robotsix-http` to listed dependencies.
- Migrate retry logic from `tenacity` to `robotsix-http`:
  - Replace `_wrap_caldav_op` tenacity-based decorator with `robotsix_http.retry.call_with_retry` + custom `is_transient_fn`.
  - Replace manual healthcheck retry loop with `robotsix_http.retry.call_with_retry`.
  - Remove `tenacity` dependency; add `robotsix-http` pinned by commit SHA.
  - Delete unused periodic presence files `security_posture.yaml` and `state_sync.yaml`.
- Update AGENT.md module layout diagram: `entrypoint.py` → `entrypoint/` subdirectory (PR #365 follow-up)
- Update AGENT.md to reflect `settings` module reorganization from `settings.py` to `settings/__init__.py`.
- Update AGENT.md module layout diagram: `healthcheck.py` → `healthcheck/__init__.py` to reflect PR #366 reorganization.)
- Moved `docs/agent/tutorials/manage-events.md` to `docs/tutorials/basic/manage-events.md` for consistent directory structure. Updated cross-references in `first-agent.md`, `tutorials/index.md`, `mkdocs.yml`, and `docs/modules.yaml` accordingly.
- Reorganize `settings` module from flat file (`settings.py`) to per-module package (`settings/__init__.py`) for symmetric module layout.
- Adopt standard Makefile targets: add `lock-check`, `pre-commit`, `test-unit`, and `test-integration`; rename `test` → `test-unit` (with `test` alias); extend `clean` to remove `.mypy_cache`, `.hypothesis`, and `site/`; include `lock-check` in `all` target.
- Reorganize `agent` module from flat file to sub-package (`src/robotsix_calendar_agent/agent/__init__.py`), aligning with the per-module layout pattern used by `caldav-client` and `intent-parser`.
- Reorganize `entrypoint` module into per-module subdirectory layout (`entrypoint.py` → `entrypoint/__init__.py`, `__main__.py` → `entrypoint/__main__.py`).
- Convert `intent_parser` from a flat module to a sub-package (`intent_parser/__init__.py`), aligning with the `caldav_client` layout pattern.
- Fix unresolved merge conflict markers in `docs/agent/tutorials/manage-events.md`
  and stale constructor-arguments claim in `README.md`.
- Removed accidentally-committed 37 MB `core` binary (ruff executable) from git tracking and added `core` to `.gitignore` to prevent re-occurrence.
- Updated README and tutorial docs to reference `config/config.json` instead of stale `RADICALE_*` environment variables, matching the `robotsix_config` migration.
- Enable `strict_markers = true` in pytest config so typo'd markers
  cause hard collection errors instead of silent warnings.
- Refactor: extract repeated span-boilerplate from `_wrap_caldav_op` exception handlers into a `_record_and_raise` helper, eliminating ~20 lines of duplicate code.
- Add missing `step-security/harden-runner` step to the `config-schema-drift` job in `ci.yml` and the `schema-drift` job in `config-schema-drift.yml`, for parity with all other hand-rolled jobs.
- Removed the stale "Component-Agent Management" intermediate tutorial
  (nav, index, and module registration) — the management plane was
  decommissioned with the `robotsix-agent-comm` broker removal.
- Add `check-json` pre-commit hook to validate JSON syntax in `config/` files at commit time.
- Migrate config from ``pydantic_settings.BaseSettings`` (env/.env) to ``robotsix_config.load_config`` (single ``config/config.json`` file, located only by ``ROBOTSIX_CONFIG_FILE``).
  Removed ``.env.example`` and ``pydantic-settings`` dependency; ``RADICALE_PASSWORD`` remains ``SecretStr`` but is now sourced from the JSON config file.
  Added ``config/config.schema.json`` and a CI drift check to keep it in sync with the ``Settings`` model.
- Fix stale module layout diagram in `AGENT.md`: show `caldav_client/` as a package directory instead of a single `.py` file, and add missing `__main__.py` and `healthcheck.py` entries.
- **BREAKING**: Migrate configuration from env vars to `config/config.json` via `robotsix_config.load_config()`.
  Settings is now a plain Pydantic `BaseModel` — `pydantic-settings` and env-var config
  are removed. The config file is located via `ROBOTSIX_CONFIG_FILE`; credentials
  (`RADICALE_PASSWORD`) are `SecretStr` fields in the config file.
  `CalendarAgent` no longer accepts `radicale_url`/`radicale_username`/`radicale_password`
  constructor arguments. Docker Compose and Dockerfile now mount the config volume
  and set `ROBOTSIX_CONFIG_FILE` instead of `RADICALE_*` env vars.
  `.env.example` is replaced by `config/config.example.json`.
  A CI drift check (`config-schema-drift.yml`) ensures `config/config.schema.json`
  stays in sync with the Settings model.
- Add configurable `CALDAV_TIMEOUT` (default 30s) to `CalDavClient`, threaded through `CalendarAgent` and the healthcheck probe, to prevent indefinite hangs when the Radicale server becomes unresponsive.
- Fix stale reference to decommissioned ``monitor`` system in `CalDavClient.health()` docstring.
- README: update configuration section to reference all six settings fields and link to `docs/configuration.md`.
- Inject current UTC date into the intent parser system prompt so that
  relative-date expressions ("next Tuesday", "this week") are resolved
  against the actual current date rather than the model's guess.
- Normalize handler signatures in `agent.py`: pre-bind `operation` strings via lambdas in `_DISPATCH` and remove the `_CREATE_UPDATE_HANDLERS` set, simplifying `_dispatch` to a single call pattern.
- Add `.gitattributes` with `linguist-generated=true merge=ours` for `uv.lock` to collapse lockfile diffs in PRs and resolve merge conflicts by keeping the current branch's version.
- Add Hypothesis profile infrastructure with CI/dev split and shared strategies in `tests/strategies.py`
- Fix stale `agent.start()`/`agent.stop()` references in docs (`docs/index.md`, `docs/agent/tutorials/manage-events.md`, `docs/tutorials/basic/first-agent.md`) and replace a broken relative link to test fixture in `first-agent.md`.
- Add supply-chain timing defense: `exclude-newer = "7d"` in `pyproject.toml` and `UV_MALWARE_CHECK=1` in CI setup-uv action.
- Enable `docstring_coverage` periodic workflow to scan for undocumented public interfaces and file draft tickets.
- Add weekly OpenSSF Scorecard workflow (`.github/workflows/scorecard.yml`) to surface security best-practice regressions.
- Fixed stale `BaseSettings` field count in AGENT.md (12 → removed count entirely to prevent future drift).
- Add hadolint Dockerfile linting to CI and pre-commit hooks
- Remove dead `_settings` attribute from `CalendarAgent` (never read after `__init__` assignment).
- Add `docs` and `docs-serve` phony targets to Makefile for building and live-previewing docs with mkdocs
- Add `make coverage` and `make coverage-view` targets for local coverage feedback, matching CI's `--cov=robotsix_calendar_agent` flags. Document both targets in `CONTRIBUTING.md`.
- Replace hand-rolled `_event_to_dict` serializer with `dataclasses.asdict()` in the event dispatch handlers. Removes the private `_event_to_dict` function and its module-level import from `agent.py`, eliminating unnecessary coupling between the top-level agent and an internal caldav_client detail.
- Modernize `.pre-commit-config.yaml`: replace deprecated `mirrors-mypy` with local `uv run mypy` hook (`language: unsupported`), fix `autofix_commit_msg` placeholder from `%s` to `{hook_id}`, and migrate vulture hook from `language: system` to `language: unsupported` with `uv run --frozen`.
- CI: Fix SBOM generation to exclude dev-only dependencies by adding `--no-dev` to `uv sync` in the `sbom` job.
- Migrate from hand-rolled pre-commit CI workflow to pre-commit.ci by adding `ci:` section to `.pre-commit-config.yaml` and removing `.github/workflows/pre-commit-ci.yml`.
- Updated AGENT.md module layout rule: `depends_on` → `dependencies` to match robotsix-modules v0.2 schema (PR #312).
- Add missing `__init__.py` files to `tests/agent/`, `tests/intent_parser/`, and `tests/settings/` for consistent test-package structure
- Add `Makefile` with standardised dev targets (`install`, `lint`, `format`, `typecheck`, `test`, `clean`, `help`, `all`); update `README.md` and `CONTRIBUTING.md` to reference `make <target>` instead of raw `uv run` commands.
- Add `TestDispatchNounVerbSync` test verifying `_OPERATION_NOUN` / `_OPERATION_VERB` cover every `_DISPATCH` key (complementing the import-time assert).
- Fix pre-existing CodeQL ``py/ineffectual-statement`` and ``py/unnecessary-lambda`` alerts in vulture_whitelist.py, test_hypothesis_roundtrip.py, calendar_ops.py, contact_ops.py, and task_ops.py.
- Remove dead `_token_required_when_enabled` entry from `vulture_whitelist.py`.
- Add import-time assert guarding `_OPERATION_NOUN` and `_OPERATION_VERB` dict completeness against `_DISPATCH` keys
- Replace custom `_setup_logging`/`_JsonFormatter` in `entrypoint` with `robotsix_llmio.logging.setup_logging`, removing ~50 lines of duplicated code and gaining OTel trace-id injection on all log lines.
- Split `tests/caldav_client/test_caldav_client.py` monolith (104 tests, 1368 lines) into per-module test files: `test_calendar_ops.py`, `test_contact_ops.py`, `test_task_ops.py`, `test_exceptions.py`, with shared fixtures extracted to `conftest.py` and `_shared` helpers moved into `test_shared.py`.
- Derive `_IntentOutput.operation` Literal type from `CalendarOperation`, `ContactOperation`, and `TaskOperation` enum values using PEP 646 unpacking (`Literal[*CalendarOperation, *ContactOperation, *TaskOperation]`) instead of a manually enumerated union, keeping the type in sync with enum members automatically.
- Replace hand-rolled ``_contact_to_dict`` / ``_task_to_dict`` in ``agent.py`` with ``dataclasses.asdict()``, and fix a syntax error in ``_shared.py`` inadvertently introduced in a prior edit.
- Remove no-op `CalendarAgent.start()` and `CalendarAgent.stop()` lifecycle shims, and simplify `__enter__`/`__exit__` to identity pattern.
- Document `depends_on` convention: module-level internal imports must be recorded in `docs/modules.yaml` via `depends_on` (AGENT.md `## Module layout`).
- Add `caldav_client` to `init.depends_on` in `docs/modules.yaml` to reflect the module-level import of `caldav_client.exceptions` in `__init__.py`.
- Updated documentation to reference Python 3.14+ instead of Python 3.12+ (CONTRIBUTING.md, docs/tutorials/basic/first-agent.md).
- Remove stale `Python :: 3.12` and `Python :: 3.13` classifiers from
  `pyproject.toml` to match `requires-python = ">=3.14"`.
- Fix `docker-compose.yml` healthcheck to use `calendar-agent-healthcheck` CLI entry point (matching Dockerfile), replacing the non-existent `/app/healthcheck.py` path.
- Consolidate `add_to_calendar_handler` module: move `_event_to_dict` into `caldav_client/_shared.py`, remove dead `handle_add_to_calendar()` function and its tests, delete the module. The only production caller (`agent.py`) now imports from `caldav_client._shared`.
- Consolidate `logging_config` module into `entrypoint`: inline `_setup_logging()` and `_JsonFormatter` as private helpers, move tests, remove module registry entry, and delete the standalone module files.
- Wire deptry as a CI job to catch unused dependency declarations, and add `deptry>=0.20` to the dev dependency group.
- Remove `OperationError` backward-compatibility alias — use `CalendarError` directly. The alias was never exercised by any `except`/`raise`/`isinstance` call in the repo.
- Harmonize `astral-sh/setup-uv` SHA across CI workflows: pin `pre-commit-ci.yml` to `e58605a9` with `# v5.4.2` matching `ci.yml`. Also fix `actions/checkout` annotation from `# v4` to `# v4.3.1`.
- Replace flat `OperationError` with a typed exception hierarchy (`CalendarError`, `NotFoundError`, `AuthError`, `RateLimitError`, `ConflictError`, `CalDAVError`, `AgentLogicError`) in `caldav_client.exceptions`. Callers can now `except` on specific error types instead of string-matching `exc.code`. `OperationError` is kept as a backward-compatible alias for `CalendarError`.
- Move `logging_config` docs from pooled `docs/reference/logging_config.md` to per-module `docs/logging_config/reference.md`, completing the per-module documentation layout migration.
- Add CodeQL (Python) taint-tracking SAST job to CI pipeline for injection-vulnerability detection (command injection, SSRF, LDAP injection, SSTI).
- Add missing `healthcheck/reference.md` and `reference/logging_config.md` entries to the Code Reference nav in `mkdocs.yml`.
- Add trailing docstrings to all `Settings` fields so mkdocstrings can
  render descriptions automatically; enable `griffe-pydantic` extension
  and replace the hand-written config table with auto-generated docs.
- Add Google-style docstring to `healthcheck.main()` documenting exit codes,
  retry behavior, and credential requirements. Add docstrings to `RETRIES` and
  `RETRY_DELAY_SECONDS` module-level constants.
- New boilerplate: `doc-recommendation-only-boilerplate.md` — documents the pattern for when the doc agent classifies a change as user-facing but determines no documentation edits are needed.
- Fix two broken relative cross-references in docs (`docs/agent/tutorials/manage-events.md` and `docs/reference/component_agent.md`) introduced when agent module docs were moved to per-module layout.
- Fix `init` module `depends_on` in `docs/modules.yaml` to match actual module-level imports: add `add_to_calendar_handler`, remove `caldav_client` and `intent_parser` (transitive via `agent`).
- Moved `docs/reference/healthcheck.md` to `docs/healthcheck/reference.md` for per-module doc layout consistency.
- Add reference documentation page for `logging_config` module (`docs/reference/logging_config.md`).
- Replace fragile substring matching in `_render_reply` with explicit `_OPERATION_NOUN` / `_OPERATION_VERB` mappings derived from the operation enum values.
- Export `handle_add_to_calendar` from the package namespace so external
  consumers can discover and import the auto-mail add-to-calendar handler.
- docs/modules.yaml: fixed broken duplicate `intent_parser` entry — removed placeholder block and set real entry's `depends_on: []`
- Enable 15 core periodic mill workflows (audit, health, agent_check, bc_check, changelog_autofill, completeness_check, copy_paste, module_curator, security_posture, state_sync, survey, test_gap, trace_review, triage_boilerplate, repo_description_sync)
- Deactivate all periodic mill workflows (remove `.robotsix-mill/periodic/*.yaml`) to pause auto-generated tickets while the board backlog is cleared.
- Reorganize `entrypoint` module docs: move `docs/reference/entrypoint.md` to `docs/entrypoint/reference.md`, consistent with per-module doc layout.
- Moved settings documentation from `docs/reference/settings.md` to `docs/settings/reference.md`, standardizing on per-module doc directories.
- Moved `intent_parser` documentation from `docs/reference/intent_parser.md` to `docs/intent_parser/reference.md` for per-module doc layout consistency.
- Move `docs/reference/caldav_client.md` to `docs/caldav_client/reference.md` to align with per-module doc layout already used by the `agent` module.
- Moved `docs/reference/add_to_calendar_handler.md` to `docs/add_to_calendar_handler/reference.md` for per-module doc layout consistency with the `agent` module.
- Add test coverage and reference documentation for the `healthcheck` module.
  - New test file `tests/healthcheck/test_healthcheck.py` covering credential-missing exit, success path, failure exhaustion, and retry logic.
  - New reference doc `docs/healthcheck/reference.md`.
  - Updated `docs/modules.yaml` to register test and doc paths.
- Added manual OpenTelemetry spans to CalDAV operations, agent dispatch, and healthcheck
  probe for improved observability of infrastructure calls.
- Removed unused backward-compatibility re-export of `_unescape_text` on `CalDavClient`; the canonical import from `._shared` via `contact_ops.py` is unaffected.
- docs/modules.yaml: Added `path`, `paths`, and `doc_paths` fields to `logging_config` entry, matching the pattern of all other module entries.
- Replace custom `logging_config` module with `robotsix_llmio.logging.setup_logging()`
  in `entrypoint.py`, removing the duplicated `JsonFormatter` and
  `configure_logging()` implementation.
- Adopt `robotsix-modules` for automated module-manifest drift detection:
  - Add `robotsix-modules` as a dev dependency.
  - Add `modules-validate` CI job (`robotsix-modules-validate docs/modules.yaml`).
  - Fix missing `paths` entry for the `agent` module.
- Move `agent` module docs to per-module layout: `docs/reference/agent.md` → `docs/agent/reference.md`, `docs/tutorials/basic/manage-events.md` → `docs/agent/tutorials/manage-events.md`; update `mkdocs.yml` nav and cross-references.
- Classify `docs/reference/component_agent.md` and `docs/tutorials/intermediate/component-agent-management.md` under the `agent` module's `doc_paths` in `docs/modules.yaml`.
- Move `healthcheck.py` from repo root into the installable package as `robotsix_calendar_agent.healthcheck`, registered as the `calendar-agent-healthcheck` console_scripts entrypoint. The Dockerfile HEALTHCHECK now uses the entrypoint directly instead of a standalone script copy.
- Added docstrings to the three public error-code constants (`ERROR_MISSING_SUBJECT`, `ERROR_MISSING_DATES`, `ERROR_INVALID_DATES`) in `add_to_calendar_handler.py`.
- Split `caldav_client.py` (864 lines) into a package with domain-specific
  modules: `calendar_ops.py`, `contact_ops.py`, `task_ops.py`, and shared
  infrastructure in `_shared.py`. The `CalDavClient` class in `__init__.py`
  inherits from mixin classes in each domain module. All public API symbols
  (`CalDavClient`, `CalendarEvent`, `Contact`, `OperationError`, `Task`)
  remain importable from `robotsix_calendar_agent.caldav_client` unchanged.
- Clarify that `langfuse_cleanup` is a framework-level periodic workflow (does not require a per-repo presence file). Remove it from the repo-specific "Periodic workflows" key-list in AGENT.md.
- Migrated secret scanning from detect-secrets to Betterleaks in pre-commit hooks.
- Removed dead telemetry counters (`_request_count`, `_error_count`, `_last_request_ts`, `_in_flight`, `_started_at`) and `monitor_snapshot()` from `CalendarAgent`. These were left over from the removed broker transport and were never incremented.
- Remove stale `CALENDAR_AGENT_TRANSPORT=brokered` env var from Dockerfile. The broker transport was removed in a past refactor; the env var was silently ignored.
- Removed stale broker-transport and component-agent configuration
  entries from `.env.example` and `docs/configuration.md`.  The
  removed variables (`BROKER_HOST`, `COMPONENT_AGENT_ENABLED`, etc.)
  no longer exist in `settings.py` — see
  `docs/reference/component_agent.md` for the removal notice.
- Restore non-broker entrypoint tests (`TestMain`, `TestServeBlocking`) that were
  incorrectly removed alongside broker-specific tests
- Remove stale "Agent-comm" language from `pyproject.toml` description and
  `docs/index.md` `agent_id` parameter doc
- Fix undefined `uid` variable in `docs/tutorials/basic/manage-events.md`
- Remove ``robotsix-agent-comm`` dependency and all broker client/responder
  code.  The ``CalendarAgent`` no longer creates an agent-comm transport;
  the ``ComponentAgentResponder`` and component-agent management kinds
  (``monitor``, ``config-get``, ``config-set``) are removed.  The
  ``add_to_calendar_handler`` retains its business logic with a local
  ``Response`` stand-in.  Broker integration will be reimplemented via
  central-deploy in a future release.
- Add ``__main__.py`` to support ``python -m robotsix_calendar_agent`` invocation, following the Uvicorn pattern.
- Move entrypoint tests from `tests/brokered_entrypoint/` (deleted) to `tests/entrypoint/test_entrypoint.py`, dropping broker-specific test classes and updating imports to `robotsix_calendar_agent.entrypoint`.
- Remove all broker-related documentation: BROKER_* env vars, brokered transport mode, brokered_entrypoint references,
  and the brokered-service tutorial — replaced with in-process-only docs and entrypoint module reference
- Remove broker transport: delete `brokered_entrypoint.py`, replace with `entrypoint.py` (in-process only); remove `BROKER_*`/`CALENDAR_AGENT_TRANSPORT`/`CALENDAR_AGENT_ID` fields from `Settings`; remove `agent` parameter from `CalendarAgent.__init__`; drop broker env vars from `docker-compose.yml`.
- Pin git version in Dockerfile apt-get install to satisfy hadolint DL3008
- Bump `requires-python` to `>=3.14` and align tooling: ruff `target-version` → `py314`,
  mypy `python_version` → `3.14`.
- Update Dockerfile base images to `python:3.14-slim-bookworm` (builder & runtime stages).
- Add `pre-commit` and `docker` ecosystems to Dependabot configuration for automated
  hook pin and base-image digest updates.
- Deduplicate `__all__` between `__init__.py` and `agent.py`: `__init__.py` now imports
  `__all__` from `agent` and extends it with `__version__`, eliminating the manual
  duplicate list that could drift.
- Extract shared resolution-instruction builder: `_build_resolution_instruction` in `add_to_calendar_handler.py` now accepts optional `description` and `location` keyword arguments, and `_build_add_to_calendar_instruction` in `agent.py` delegates to it instead of duplicating the prompt construction. This eliminates drift between the two call sites.
- Add Dependabot auto-merge caller workflow (`.github/workflows/dependabot-auto-merge.yml`).
- Remove dead `_DEFAULT_AGENT_ID` constant from `brokered_entrypoint.py` — all callers use `Settings.CALENDAR_AGENT_ID` since commit `962b0ed`.
- Add maintenance triage boilerplate: documents the CI failure routing pattern with action verbs (`fork_repo`, `noop`, `notify`), decision criteria, and spawning conventions.
- Add triage SKIP boilerplate pattern (`.robotsix-mill/boilerplate/triage-skip-boilerplate.md`) — defines when to fast-path implementation-ready drafts past the refine stage.
- Add `triage_boilerplate` periodic workflow presence file (`.robotsix-mill/periodic/triage_boilerplate.yaml`) to enable the boilerplate response template scanning workflow.
- Fix stale operation count in docs: update "8 operations" → "10 operations" and add missing `list_calendars` and `list_tasks` rows to the operations reference table.
- Add robotsix stack standards reference link to README.md and AGENT.md.
- Suppress Ruff T201 (print) for `healthcheck.py` — this is a standalone CLI script where `print()` is intentional output, not debug scaffolding.
- Enable Ruff `T10` (debugger statement) and `EXE` (shebang/executable) rule families; make `healthcheck.py` executable to satisfy `EXE` shebang check.
- Fix stale operation count in `intent_parser` module docstring (8 → 10) to reflect all calendar, contact, and task operation types.
- Migrate `ConfigContractError` from local definition to `robotsix_agent_comm.protocol.ConfigContractError`; bump `robotsix-agent-comm` pin to include the canonical implementation.
# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `reference/logging_config.md` entry in `mkdocs.yml` nav under "Code Reference"
- Classify `docs/tutorials/basic/manage-events.md` under the `agent` module in `docs/modules.yaml`.
- Map caldav-specific exceptions (`NotFoundError`, `RateLimitError`, `EtagMismatchError`, `AuthorizationError`) to distinct `OperationError` codes in `_wrap_caldav_op`.

### Removed
- Dead code: `_read_value` function in `config_contract.py` (never called)

### Fixed
- Classified `docs/tutorials/intermediate/brokered-service.md` under the
  `brokered_entrypoint` module in `docs/modules.yaml`

### Changed
- Classified `docs/tutorials/basic/first-agent.md` under the `init` module
  in `docs/modules.yaml`.
- Moved `tests/test_logging_config.py` into `tests/logging_config/`
  subdirectory to match the module-mirroring convention followed by all
  other test modules.

### Fixed
- Resolved mypy errors in `healthcheck.py`, `vulture_whitelist.py`, and
  `tests/intent_parser/test_intent_parser.py` that were causing the CI
  job to fail.
- Fixed wrong Python version prerequisite (3.14+ → 3.12+) in `docs/tutorials/basic/first-agent.md`, and replaced private `_build_component_responder` usage with the public `ComponentAgentResponder` constructor in `docs/tutorials/intermediate/component-agent-management.md`.

### Added
- Four tutorials in `docs/tutorials/`: first agent, calendar event CRUD,
  brokered service deployment, and component-agent management.
- Moved `logging_config` tests into per-module subdirectory
  `tests/logging_config/` (consistent with all other modules) and added
  reference documentation at `docs/reference/logging_config.md`.
- Configurable log level via `LOG_LEVEL` env var (default `INFO`) and
  structured JSON log output via `JSON_LOGS` env var (default `false`).
- Coverage report CI job with HTML artifact upload, PR coverage comments
  via `python-coverage-comment-action`, and auto-generated coverage badge
  on main.

### Fixed
- Extract ISO 8601 parsing and time-ordering validation from `handle_add_to_calendar` into a dedicated `_parse_and_validate_iso_dates` helper, reducing the handler by ~22 lines.
- Removed spurious `agent` dependency from `component_agent` module entry in `docs/modules.yaml`.
- **vCard round-trip serialization:** Added `_unescape_text` helper to reverse `_escape_text` escaping, and fixed `_to_contact` to properly unescape vCard field values (FN, EMAIL, TEL, UID). Also replaced naive `ADR` semicolon-split with an escape-aware single-pass parser, and removed `value.strip()` that was silently dropping whitespace-only field values.

### Changed
- Bumped pre-commit hooks to latest versions: `pre-commit-hooks` v5.0.0→v6.0.0, `ruff-pre-commit` v0.15.15→v0.15.20, `mirrors-mypy` v1.19.1→v2.1.0, `actionlint` v1.7.7→v1.7.12, `commitizen` v4.6.0→v4.16.4.
- Merged `add_to_calendar` bypass in `agent.py` into the standard parse → dispatch → render pipeline: the structured payload is now converted to a synthetic natural-language instruction and fed through `_intent_parser.parse()` → `_dispatch()` → `_render_reply()`, eliminating the standalone `handle_add_to_calendar` call from the request handler.
- Extracted shared `_find_event_by_uid` helper in `CalDavClient` to eliminate duplicated UID-lookup logic in `update_event` and `delete_event`.
- Enabled Ruff `S` (flake8-bandit) rules in `pyproject.toml` and removed the slower `bandit` pre-commit hook.

### Added
- Hypothesis property-based round-trip tests for calendar event, task, and contact serialization against the in-process Radicale fixture.
- `actionlint` job in CI (`.github/workflows/ci.yml`) and pre-commit hook (`.pre-commit-config.yaml`) for workflow syntax validation and shellcheck on inline scripts.
- Commitizen (`commitizen>=4,<5`) dev dependency for automated semantic version bumping, changelog generation, and conventional-commit enforcement.
- `[tool.commitizen]` configuration in `pyproject.toml` targeting both version locations (`pyproject.toml:version` and `src/robotsix_calendar_agent/__init__.py`), with changelog generation and incremental mode enabled.
- Commitizen pre-commit hook in `.pre-commit-config.yaml` to enforce Conventional Commits message format.
- Commitizen PR title check in CI (`ci.yml`) to gate non-conventional PR titles.
- Docker `HEALTHCHECK` via `healthcheck.py` that validates CalDAV reachability using the existing `CalDavClient.health()` probe.
- Registered `docs/modules.yaml` under the `init` module's `doc_paths`.
- Extracted `_iter_config_fields` helper in `config_contract.py` to deduplicate settings-iteration loops across `get_config_snapshot` and `describe_config`.

### Fixed
- Fixed `brokered_entrypoint` entry in `docs/modules.yaml`: added missing `settings` and `component_agent` to `depends_on`.
- Fixed `intent_parser` entry in `docs/modules.yaml`: added missing `path` key, added `test_paths` key, and moved test files out of `paths` to match conventions of other module entries.
- Added missing `reference/component_agent.md` to `mkdocs.yml` navigation under Code Reference.
- `brokered_entrypoint.py`: removed unreachable `if not token:` guard in `_build_component_responder` (token-empty invariant is already enforced by `ComponentAgentSettings`). Added test coverage for the enabled-with-token path.

### Changed
- Removed dead `if TYPE_CHECKING: pass` blocks and unused `TYPE_CHECKING` imports from `agent.py` and `caldav_client.py`.
- `__init__.py`: re-exported symbols now flow through `agent.py` instead of
  duplicating imports from `.caldav_client` and `.intent_parser`.
- Merged `component_agent/responder.py` into `brokered_entrypoint.py`:
  `ComponentAgentResponder` and `COMPONENT_KINDS` now live alongside the
  brokered lifecycle, eliminating the deferred/lazy import dance between
  the two modules.
- `agent.py`: removed unused `operation` parameter from six dispatch handlers
  (`_handle_list_events`, `_handle_list_tasks`, `_handle_list_calendars`,
  `_handle_delete_event`, `_handle_list_contacts`, `_handle_delete_contact`);
  `_dispatch` now only passes `operation` to the two create/update handlers
  that forward it to `_entity_op`.
- `caldav_client.py`: lifted duplicated inner closures `_text` / `_dt` from
  `_to_calendar_event` and `_to_task` into module-level helpers `_comp_text`
  and `_comp_dt`.
- `intent_parser.py`: replaced `get_provider` + `provider.build_agent(level=2)` with `build_agent_for_level(2, ...)` to match current `robotsix-llmio` API.
- Hardened Dockerfile: pinned base images to digest, added uv package cache
  mount, cleaned apt lists in builder stage, and replaced `RUN chown` with
  `COPY --chown` to eliminate an unnecessary layer.
- Bumped `robotsix-llmio` to include the PromptedOutput auto-wrap fix for
  reasoning tiers, preventing "Thinking mode does not support this tool_choice"

### Fixed
- Added missing `RADICALE_DEFAULT_CALENDAR` commented entry to `.env.example`.
- Fix `_entity_op` bug where a create operation with an incidental `uid` in
  params was silently dispatched as an update. The dispatch now uses only the
  `operation` string to decide between create/update.
- Component-agent responder delegation in `_handle_request_impl` now catches
  unexpected exceptions and returns an `Error` response instead of letting them
  propagate unhandled.
- Updated `_INTENT_SYSTEM_PROMPT` to instruct the LLM to omit the `uid` key
  (rather than leaving it empty) when a UID is needed but not provided — the
  handler already rejects empty UIDs, so the old prompt was misleading the model.
  errors when using `level=2` with raw pydantic `output_type`.

### Added
- Added `COMPONENT_AGENT_ENABLED`, `COMPONENT_AGENT_TOKEN`, and
  `COMPONENT_AGENT_ID` commented entries to `.env.example` for discoverability.

- Added `list_tasks` operation: the calendar agent can now list VTODO tasks
  from a CalDAV calendar via a new `Task` dataclass, `CalDavClient.list_tasks()`,
  and `list_tasks` intent classifier support. Fixes broken `query_tasks` channel
  that was incorrectly routing to the CardDAV contacts API.

- Added `workflow-audit` CI job that runs zizmor to audit workflow files for security anti-patterns, with SARIF output uploaded to the Security tab.
- Pinned `actions/checkout` and `actions/dependency-review-action` in the `dependency-review` job to immutable SHAs (fixes a pre-existing zizmor finding).

- Enable Ruff's `RUF` rule set and remove three stale `# noqa: BLE001` suppressions.
- Added `fail_under = 85` to `[tool.coverage.report]` in `pyproject.toml` so local `pytest --cov` runs enforce the same 85% coverage threshold as CI.

- Expand `SECURITY.md` with supported versions table and disclosure policy.

- Initial scaffold: calendar/contacts agent with agent-comm + llmio.
- Pre-commit CI workflow (`pre-commit-ci.yml`) to enforce hooks in CI.
- Langfuse tracing via `robotsix-llmio[tracing]` extra for OpenTelemetry export.
- Dependency-review-action in CI pipeline for supply-chain gate on PRs.
- Auto-generated API reference documentation for all public modules.
- `docs/configuration.md` documenting all 12 `BaseSettings` environment variables.
- Tenacity-based retry logic (`tenacity>=9.0`) to `CalDavClient` for transient
  network failures on CalDAV/CardDAV operations.
- `AGENT.md` with repo-specific agent conventions for mill workflows.
- Unit tests for `settings.py` (`tests/test_settings.py`).
- `env_doc_sync` periodic workflow enabled to enforce `settings.py` ↔
  `docs/configuration.md` consistency.

### Changed

- Dockerfile hardened with multi-stage build, non-root user, BuildKit cache
  mounts, and UV optimizations.
- `docker-publish.yml` migrated to consume mill's reusable `docker-release.yml`.
- All GitHub Actions and reusable workflow references pinned to immutable
  SHA digests.
- Decomposed 140-line `handle_add_to_calendar` function into smaller, focused
  phases: `_parse_email_payload`, `_extract_json_payload`,
  `_parse_and_validate_event`, `_apply_defaults`, and `_register_handlers`.
- DRY duplicate delete handler functions via a single `_delete_entity_op`
  helper shared by `_handle_delete_event` and `_handle_delete_contact`.
- `_IntentOutput.operation` changed from `str` to `Literal["create", "update",
  "delete", "list"]` to strengthen structured-output enum constraints.
- Collapsed identical create/update handler wrappers into single functions
  each (`_handle_create_or_update_event`, `_handle_create_or_update_contact`).
- Refactored environment variable configuration with `pydantic-settings` for
  type-safe, centralized config management via `Settings` class.
- Reorganized `add_to_calendar_handler`, `caldav_client`, and
  `brokered_entrypoint` modules to per-module layout (src/docs/tests).
- Calendar agent now driven via the shared `BrokeredAgent` from
  `robotsix-agent-comm`.
- CalDAV read-back now uses `icalendar_instance`, dropping the `vobject`
  dependency.
- `deps-bump.yml` reusable workflow adopted for automated dependency bumps.
- Agent responses now emit a human-readable `reply` alongside the structured
  `result`.

### Fixed

- `_entity_op` no longer silently creates an entity when the LLM omits the
  `uid` key from an update operation's params. The operation type is now
  threaded through the dispatch layer to detect update intents and require a
  non-empty `uid`.
- Pre-commit CI failures: bandit B101 (assert), B105 (token variable name),
  mypy untyped-decorator on pydantic field validators, and detect-secrets false
  positives on workflow commit SHAs and test strings.
- `list_events` and `list_contacts` docstrings corrected: implementation
  searches only the first/default address book / calendar, not "all".
- `delete_event` docstring corrected: implementation raises on not-found
  (not idempotent) — docstring now matches behaviour.
- `BROKER_CLIENT_CERT` and `BROKER_CLIENT_KEY` now correctly wired into
  `_build_brokered_agent` so mTLS client certificates are actually used.
- Dispatch handlers now validate that `uid` is non-empty for update/delete
  operations (the LLM prompt previously said "leave it empty").
- `docs.yml` permissions fixed for `mkdocs gh-deploy`: `contents:write`
  instead of `contents:read`.
- Error-handling lint findings resolved across all six source modules.
- Removed unused `client` parameter from `_entity_op` in `agent.py`.
- `BROKER_PORT` default mismatch between docs and code fixed.
- Docker build: stale Python base-image digest pin fixed.
- Intent parser corrected to use the llmio agent API with the non-reasoning
  tier.
- CalDAV operations now emit valid iCalendar datetimes for recurrence rules
  and all-day events.
- `llmio` provider extra installed so the intent-parser agent can resolve
  its model provider at runtime.
