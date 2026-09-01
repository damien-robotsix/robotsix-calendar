"""Tests for the robotsix-ui dashboard (app shell + visualisation)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from robotsix_calendar.api import app


@pytest.fixture
def client() -> TestClient:
    """Build a TestClient for the shared FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


class TestDashboardPage:
    def test_root_serves_robotsix_ui_access_point(self, client: TestClient) -> None:
        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "/static/robotsix-ui.css" in response.text
        assert "/static/robotsix-ui-vanilla.js" in response.text
        assert "mountAppShell" in response.text

    def test_dashboard_mounts_app_shell_with_navigation(
        self, client: TestClient
    ) -> None:
        body = client.get("/").text

        assert 'brand: "robotsix-calendar"' in body
        assert "navItems" in body
        assert 'href: "/settings"' in body
        assert 'mountAppShell(document.getElementById("app")' in body

    def test_dashboard_visualises_calendars_and_contacts(
        self, client: TestClient
    ) -> None:
        body = client.get("/").text

        assert 'fetch("/calendars")' in body
        assert 'fetch("/contacts")' in body
        assert 'id="calendar-list"' in body
        assert 'id="contacts-table"' in body
