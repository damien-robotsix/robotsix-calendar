"""Security response headers emitted by the API (http-security-headers)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from robotsix_calendar.api import app
from robotsix_calendar.api._ui_pages import inline_script_hashes


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("path", ["/ui", "/ui/events", "/settings", "/health"])
def test_security_headers_present(client: TestClient, path: str) -> None:
    response = client.get(path)

    headers = response.headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "SAMEORIGIN"
    assert headers["strict-transport-security"].startswith("max-age=31536000")
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in headers
    assert headers["cache-control"] == "no-store, max-age=0"


def test_csp_allows_inline_scripts_only_by_hash(client: TestClient) -> None:
    csp = client.get("/ui/events").headers["content-security-policy"]

    assert "default-src 'self'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src ", 1)[1].split(";", 1)[0]
    for source in inline_script_hashes():
        assert source in csp
