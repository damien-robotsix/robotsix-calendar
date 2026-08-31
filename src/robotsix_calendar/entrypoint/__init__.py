"""Long-lived in-process service entrypoint for :class:`CalendarAgent`.

Blocks until ``SIGTERM``/``SIGINT`` requests a graceful shutdown.
"""

from __future__ import annotations

import logging
import signal
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..settings import Settings

logger = logging.getLogger(__name__)

__all__ = ["main"]


def _serve_blocking() -> None:
    """Block until ``SIGTERM``/``SIGINT`` (in-process mode)."""
    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d; shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("CalendarAgent service running; awaiting shutdown signal")
    try:
        stop_event.wait()
    finally:
        logger.info("CalendarAgent service stopped")


def _start_http_server(settings: Settings) -> None:
    """Start the FastAPI HTTP server in a daemon thread on port 8080."""
    import threading

    import uvicorn

    from ..api import app
    from ..caldav_client import CalDavClient

    client = CalDavClient(
        url=settings.RADICALE_URL,
        username=settings.RADICALE_USERNAME,
        password=settings.RADICALE_PASSWORD.get_secret_value(),
        default_calendar=settings.RADICALE_DEFAULT_CALENDAR,
        timeout=settings.CALDAV_TIMEOUT,
    )
    app.state.caldav_client = client

    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")  # noqa: S104  # nosec B104
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    logger.info("HTTP API server started on port 8080")


def main() -> None:
    """Run the calendar agent as a long-lived in-process service."""
    from robotsix_config import load_config
    from robotsix_llmio.logging import setup_logging

    from ..settings import Settings

    settings = load_config(Settings)

    # Wire canonical Langfuse/OpenRouter credentials before any llmio/SDK
    # use in the real runtime path (the entrypoint never constructs
    # CalendarAgent).
    from ..agent import _setup_runtime_credentials

    _setup_runtime_credentials(settings)

    setup_logging(
        level=settings.LOG_LEVEL,
        fmt="json" if settings.JSON_LOGS else "console",
        loggers=("robotsix_calendar",),
    )
    _start_http_server(settings)
    _serve_blocking()
