# syntax=docker/dockerfile:1

# Builder stage: installs build dependencies and creates the virtualenv.
FROM python:3.14-slim-bookworm AS builder

# Install uv from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /bin/

# git is required: robotsix-llmio is a git dependency that uv fetches at build time.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends git=1:2.39.5-0+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Optimize uv for Docker builds.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# First layer: install only dependencies (cached unless pyproject.toml/uv.lock change).
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Second layer: copy source and install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Runtime stage: minimal image with only the virtualenv and source.
FROM python:3.14-slim-bookworm AS runtime

# Upgrade vulnerable system packages, then remove pip (not needed at
# runtime).  Removing pip also removes its vendored msgpack 1.1.2 which
# triggers GHSA-6v7p-g79w-8964.  setuptools<78.1.1 has CVE-2025-47273.
RUN python -m pip install --no-cache-dir --upgrade 'setuptools>=78.1.1' \
    && find /usr/local/lib/python3.14/site-packages \
        -maxdepth 1 \( -name 'pip' -o -name 'pip-*.dist-info' \) \
        -exec rm -rf {} + \
    && rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14

# Create a dedicated non-root user. uid/gid 1000 is the fleet convention
# (chat/auto-mail/mill): the shared claude-auth volume central-deploy mounts
# for the claudeSDK transport is owned by uid 1000 with mode 700, so any
# other uid cannot read the credentials.
RUN groupadd -g 1000 app && useradd -u 1000 -g app -m -d /app -s /bin/false app

WORKDIR /app

# Copy the virtualenv, source, config, and healthcheck from the builder.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/config /app/config

# Create config directory for volume mount.
RUN mkdir -p /app/config && chown app:app /app/config

# Runtime configuration.
ENV PATH="/app/.venv/bin:${PATH}" \
    ROBOTSIX_CONFIG_FILE=/app/config/config.json

USER 1000

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["calendar-agent-healthcheck"]

CMD ["calendar-agent"]
