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
from typing import Any

from opentelemetry import trace
from robotsix_config import load_config
from robotsix_http.retry import RetryConfig, call_with_retry

from robotsix_calendar_agent.caldav_client import CalDavClient
from robotsix_calendar_agent.settings import Settings

_tracer = trace.get_tracer(__name__)


def main() -> None:
    """Run the Docker HEALTHCHECK probe.

    Validates CalDAV reachability using credentials from the config file.
    Sets OpenTelemetry spans for each attempt. Exits with code 0 on success
    or 1 if all retry attempts fail.

    Exit codes:
        0: CalDAV server is reachable and responsive.
        1: Health probe failed after all retry attempts.

    The probe retries with exponential backoff via
    :func:`robotsix_http.retry.call_with_retry`. Requires
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

    def _probe() -> dict[str, Any]:
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
                span.set_attribute("healthcheck.result", "error")
                span.set_attribute("error", True)
                span.record_exception(exc)
                raise
            else:
                if result.get("connected"):
                    span.set_attribute("healthcheck.result", "ok")
                    return result
                else:
                    span.set_attribute("healthcheck.result", "failed")
                    span.set_attribute("error", True)
                    raise RuntimeError(result.get("error", "unknown error"))

    try:
        result = call_with_retry(
            _probe,
            config=RetryConfig(max_retries=3),
            what="healthcheck",
        )
        print(f"healthcheck OK: {result}")
        sys.exit(0)
    except Exception as exc:
        print(
            f"healthcheck FAILED after retries: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
