"""Docker HEALTHCHECK probe — validates CalDAV reachability.

Loads credentials from the same config file the agent uses,
creates a :class:`~robotsix_calendar_agent.caldav_client.CalDavClient`,
and calls :meth:`~robotsix_calendar_agent.caldav_client.CalDavClient.health`.

Exit codes:
    0 — CalDAV server is reachable and responsive.
    1 — health probe failed after retries.
"""

from __future__ import annotations

import sys
import time

from opentelemetry import trace
from robotsix_config import load_config

from robotsix_calendar_agent.caldav_client import CalDavClient
from robotsix_calendar_agent.settings import Settings

RETRIES = 3
"""Number of health-check retry attempts before giving up."""

RETRY_DELAY_SECONDS = 2
"""Seconds to wait between health-check retry attempts."""

_tracer = trace.get_tracer(__name__)


def main() -> None:
    """Run the Docker HEALTHCHECK probe.

    Validates CalDAV reachability using credentials from the config file.
    Sets OpenTelemetry spans for each attempt. Exits with code 0 on success
    or 1 if all retry attempts fail.

    Exit codes:
        0: CalDAV server is reachable and responsive.
        1: Health probe failed after all retry attempts.

    The probe retries up to :data:`RETRIES` times (3 attempts) with
    :data:`RETRY_DELAY_SECONDS` (2 seconds) between attempts. Requires
    ``RADICALE_URL``, ``RADICALE_USERNAME``, and ``RADICALE_PASSWORD`` to
    be set in the config file.
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

    last_error: str | None = None

    for attempt in range(1, RETRIES + 1):
        ok = False
        with _tracer.start_as_current_span("healthcheck.probe") as span:
            try:
                client = CalDavClient(
                    url=url,
                    username=username,
                    password=password,
                    default_calendar=default_calendar,
                    timeout=settings.CALDAV_TIMEOUT,
                )
                result = client.health()
            except Exception as exc:
                last_error = str(exc)
                span.set_attribute("healthcheck.result", "error")
                span.set_attribute("error", True)
                span.record_exception(exc)
            else:
                if result.get("connected"):
                    span.set_attribute("healthcheck.result", "ok")
                    ok = True
                else:
                    last_error = result.get("error", "unknown error")
                    span.set_attribute("healthcheck.result", "failed")
                    span.set_attribute("error", True)

        if ok:
            print(f"healthcheck OK: {result}")
            sys.exit(0)

        if attempt < RETRIES:
            print(
                f"healthcheck attempt {attempt}/{RETRIES} failed: {last_error}",
                file=sys.stderr,
            )
            time.sleep(RETRY_DELAY_SECONDS)

    print(
        f"healthcheck FAILED after {RETRIES} attempts: {last_error}",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
