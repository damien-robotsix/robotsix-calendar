"""Tests for the robotsix-ui UI access point (shared AppShell pages)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from robotsix_calendar.api import app

# Every UI page must mount the shared AppShell with the primary nav
# entries (Events, Calendars, Contacts, Settings).
UI_PAGES = ("/ui", "/ui/calendars", "/ui/contacts", "/ui/events", "/settings")


@pytest.fixture
def client() -> TestClient:
    """Build a TestClient for the shared FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


class TestRootRedirect:
    def test_root_redirects_to_ui(self, client: TestClient) -> None:
        response = client.get("/", follow_redirects=False)

        assert response.status_code == 307
        assert response.headers["location"] == "/ui"

    def test_root_follows_to_ui_landing(self, client: TestClient) -> None:
        response = client.get("/")

        assert response.status_code == 200
        assert "mountAppShell" in response.text


class TestUiPages:
    @pytest.mark.parametrize("path", UI_PAGES)
    def test_ui_page_serves_robotsix_ui(self, client: TestClient, path: str) -> None:
        response = client.get(path)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "/static/robotsix-ui.css" in response.text
        assert "/static/robotsix-ui-vanilla.js" in response.text
        assert "mountAppShell" in response.text

    @pytest.mark.parametrize("path", UI_PAGES)
    def test_ui_page_mounts_app_shell_with_navigation(
        self, client: TestClient, path: str
    ) -> None:
        body = client.get(path).text

        assert 'brand: "Calendar"' in body
        assert 'href: "/ui/events"' in body
        assert 'href: "/ui/calendars"' in body
        assert 'href: "/ui/contacts"' in body
        assert 'href: "/settings"' in body
        assert 'settingsHref: "/settings"' in body


class TestSpecificPages:
    def test_calendars_page_fetches_calendars(self, client: TestClient) -> None:
        body = client.get("/ui/calendars").text

        assert 'fetch("/calendars")' in body
        assert 'id="calendar-list"' in body
        assert 'href="/ui/events?calendar=' in body

    def test_events_page_fetches_events(self, client: TestClient) -> None:
        body = client.get("/ui/events").text

        assert 'fetch("/events?"' in body
        assert "URLSearchParams({ start: start, end: end })" in body
        assert 'id="event-list"' in body
        assert 'id="event-calendar"' in body
        assert "No events in this range" in body
        assert "Failed to load events" in body
        assert "ev.dtstart" in body
        assert "ev.dtend" in body
        assert "ev.summary" in body
        assert "ev.location" in body
        assert "ev.description" in body
        assert "escapeHtml" in body

    def test_contacts_page_fetches_contacts(self, client: TestClient) -> None:
        body = client.get("/ui/contacts").text

        assert 'fetch("/contacts")' in body
        assert "contact.full_name" in body
        assert "contact.addressbook_id" in body

    def test_settings_mounts_config_panel(self, client: TestClient) -> None:
        body = client.get("/settings").text

        assert "mountConfigPanel" in body
