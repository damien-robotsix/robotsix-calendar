.DEFAULT_GOAL := all

.PHONY: all
all: lock-check lint typecheck test  ## Run all checks (default goal)

.PHONY: lock-check
lock-check:  ## Validate uv.lock is consistent with pyproject.toml
	uv lock --check

.PHONY: install
install: .venv  ## Install dev environment and pre-commit hooks
	uv sync --frozen --group dev
	pre-commit install

.PHONY: pre-commit
pre-commit: .venv  ## Run all pre-commit hooks
	uv run pre-commit run --all-files

.venv:
	uv venv

.PHONY: lint
lint: .venv  ## Run linter and format check
	uv run ruff check src/
	uv run ruff format --check src/

.PHONY: format
format: .venv  ## Auto-format source code
	uv run ruff check --fix src/
	uv run ruff format src/

.PHONY: typecheck
typecheck: .venv  ## Run mypy static type checker
	uv run mypy src/

.PHONY: test-unit
test-unit: .venv  ## Run unit tests (non-integration)
	uv run pytest -m 'not integration' tests/

.PHONY: test-integration
test-integration: .venv  ## Run integration tests (uses an in-process Radicale server)
	uv run pytest -m integration tests/

.PHONY: test
test: test-unit  ## Run unit tests (default test target)

.PHONY: coverage
coverage: .venv  ## Run tests with coverage report
	uv run pytest --cov=robotsix_calendar_agent --cov-report=html --cov-report=term \
		-m 'not integration' tests/

.PHONY: coverage-view
coverage-view: coverage  ## Run tests with coverage and open HTML report
	open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || true

.PHONY: docs
docs: .venv  ## Build documentation with mkdocs
	uv run mkdocs build

.PHONY: docs-serve
docs-serve: .venv  ## Serve documentation locally with live reload
	uv run mkdocs serve

.PHONY: clean
clean:  ## Remove caches and build artifacts
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache .hypothesis htmlcov site build dist *.egg-info

.PHONY: help
help:  ## Display this help message
	@grep -E '^.PHONY: .*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ".PHONY: |## "}; {printf "\033[36m%-19s\033[0m %s\n", $$2, $$3}'
