"""Docker HEALTHCHECK probe — validates CalDAV reachability.

Loads credentials from the same config file the agent uses,
creates a :class:`~robotsix_calendar_agent.caldav_client.CalDavClient`,
and calls :meth:`~robotsix_calendar_agent.caldav_client.CalDavClient.health`.

Exit codes:
    0 — CalDAV server is reachable and responsive.
    1 — health probe failed.

The probe makes a single fast attempt with a short timeout so it
completes well within Docker's ``--timeout=10s``. Docker's own
``--retries=3 --interval=30s`` handles transient failures across
healthcheck invocations — the probe does not retry internally.
"""

from __future__ import annotations

import sys

from opentelemetry import trace
from robotsix_config import load_config

from robotsix_calendar_agent.caldav_client import CalDavClient
from robotsix_calendar_agent.settings import Settings

__all__ = ["main"]

_tracer = trace.get_tracer(__name__)


def main() -> None:
    """Run the Docker HEALTHCHECK probe.

    Validates CalDAV reachability using credentials from the config file.
    Sets an OpenTelemetry span for the attempt. Exits with code 0 on
    success or 1 on failure.

    Exit codes:
        0: CalDAV server is reachable and responsive.
        1: Health probe failed.

    Uses ``CALDAV_HEALTHCHECK_TIMEOUT`` (default 5s) to stay inside
    Docker's ``--timeout=10s`` window. Does **not** retry internally —
    Docker's own ``--retries`` and ``--interval`` handle transient
    failures across invocations.
    """
    settings = load_config(Settings)
    url = settings.RADICALE_URL
    username = settings.RADICALE_USERNAME
    password = settings.RADICALE_PASSWORD.get_secret_value()
    default_calendar = settings.RADICALE_DEFAULT_CALENDAR

    if not url or not username or not password:
        print(
            "healthcheck: RADICALE_URL, RADICALE_USERNAME, and "
            "RADICALE_PASSWORD must be set in config/config.json",
            file=sys.stderr,
        )
        sys.exit(1)

    with _tracer.start_as_current_span("healthcheck.probe") as span:
        try:
            client = CalDavClient(
                url=url,
                username=username,
                password=password,
                default_calendar=default_calendar,
                timeout=settings.CALDAV_HEALTHCHECK_TIMEOUT,
            )
            result = client.health()
        except Exception as exc:
            span.set_attribute("healthcheck.result", "error")
            span.set_attribute("error", True)
            span.record_exception(exc)
            print(
                f"healthcheck FAILED: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            if result.get("connected"):
                span.set_attribute("healthcheck.result", "ok")
                print(f"healthcheck OK: {result}")
                sys.exit(0)
            else:
                span.set_attribute("healthcheck.result", "failed")
                span.set_attribute("error", True)
                print(
                    f"healthcheck FAILED: {result.get('error', 'unknown error')}",
                    file=sys.stderr,
                )
                sys.exit(1)


if __name__ == "__main__":
    main()
