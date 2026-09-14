"""Tests for the FastAPI HTTP API endpoints."""

from __future__ import annotations

import contextlib
import re
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from robotsix_calendar.api import app
from robotsix_calendar.caldav_client._shared import (
    CalendarEvent,
    Contact,
    Task,
)
from robotsix_calendar.caldav_client.exceptions import (
    AgentLogicError,
    AuthError,
    CalDAVError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# Route-sync helpers — keep the /chat-skill doc and the real routes in lockstep
# ---------------------------------------------------------------------------

_ROUTE_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


def _normalize_path(path: str) -> str:
    """Collapse ``{name}``/``<name>`` path params to a common marker.

    The skill doc writes uid params as ``<uid>`` in code blocks and
    ``{uid}`` in headers, while FastAPI registers ``{uid}``; normalizing
    both lets the two representations compare equal.
    """
    return re.sub(r"[<{][^>}]*[>}]", "{id}", path).rstrip("/") or "/"


def _walk_routes(routes: object) -> list[object]:
    """Flatten every leaf route, recursing into included sub-routers.

    FastAPI's ``include_router`` (>= 0.141) no longer copies a router's
    routes onto ``app.routes``; instead it appends a single
    ``_IncludedRouter`` wrapper whose nested routes are reachable only via
    its ``original_router``. Iterating ``app.routes`` alone therefore
    misses ``/settings``, ``/chat-skill`` and the ``/ui`` pages. Recurse
    through ``original_router`` so route enumeration sees them.
    """
    leaves: list[object] = []
    for route in routes:  # type: ignore[attr-defined]
        original = getattr(route, "original_router", None)
        if original is not None:
            leaves.extend(_walk_routes(original.routes))
            continue
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path and methods:
            leaves.append(route)
    return leaves


def _public_crud_routes() -> set[tuple[str, str]]:
    """Enumerate the public CRUD ``(method, path)`` routes.

    Excludes the UI (``/ui``), static assets (``/static``), the settings
    page (``/settings``), the config surface (``/config*``), and the infra
    endpoints (``/``, ``/health``, ``/chat-skill``) — none of which the
    chat skill documents as CRUD endpoints.
    """
    excluded_exact = {
        "/",
        "/health",
        "/chat-skill",
        "/settings",
        "/openapi.json",
    }
    excluded_prefixes = ("/ui", "/static", "/config", "/docs", "/redoc")
    routes: set[tuple[str, str]] = set()
    for route in _walk_routes(app.routes):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        if path in excluded_exact or path.startswith(excluded_prefixes):
            continue
        for method in methods:
            if method in _ROUTE_METHODS:
                routes.add((method, path))
    return routes


def _registered_routes() -> set[tuple[str, str]]:
    """All registered ``(method, normalized-path)`` pairs on the app."""
    routes: set[tuple[str, str]] = set()
    for route in _walk_routes(app.routes):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            if method in _ROUTE_METHODS:
                routes.add((method, _normalize_path(path)))
    return routes


def _documented_routes(body: str) -> set[tuple[str, str]]:
    """Extract ``(method, normalized-path)`` pairs documented in the skill."""
    found: set[tuple[str, str]] = set()
    for method, path in re.findall(
        r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[A-Za-z0-9_/{}<>-]*)", body
    ):
        found.add((method, _normalize_path(path)))
    return found


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock CalDavClient."""
    return MagicMock()


@pytest.fixture
def client(mock_client: MagicMock) -> TestClient:
    """Create a TestClient with a mocked CalDavClient on app.state."""
    app.state.caldav_client = mock_client
    with TestClient(app) as c:
        yield c
    with contextlib.suppress(AttributeError):
        del app.state.caldav_client


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Chat skill
# ---------------------------------------------------------------------------


class TestChatSkill:
    def test_chat_skill_returns_markdown(self, client: TestClient) -> None:
        """GET /chat-skill returns a SKILL.md document with YAML frontmatter."""
        response = client.get("/chat-skill")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        body = response.text
        assert body.startswith("---\nname: robotsix-calendar")
        assert "## robotsix-calendar — Chat Agent Skill" in body

    def test_chat_skill_documents_every_crud_route(self, client: TestClient) -> None:
        """Every registered public CRUD route appears verbatim in the skill.

        Enumerates ``app.routes`` (rather than a hand-picked subset) so
        adding or renaming an endpoint without updating the skill doc
        fails CI instead of silently drifting.
        """
        body = client.get("/chat-skill").text
        crud = _public_crud_routes()
        assert crud, "no public CRUD routes discovered — enumeration is broken"
        missing = sorted(
            f"{method} {path}"
            for method, path in crud
            if f"{method} {path}" not in body
        )
        assert not missing, f"routes absent from /chat-skill: {missing}"

    def test_chat_skill_routes_all_resolve(self, client: TestClient) -> None:
        """Every route documented in the skill resolves to a registered route.

        Guards the reverse direction: removing or renaming an endpoint
        must not leave stale documentation behind in the skill body.
        """
        body = client.get("/chat-skill").text
        registered = _registered_routes()
        documented = _documented_routes(body)
        assert documented, "no routes parsed from /chat-skill — parser is broken"
        stale = sorted(
            f"{method} {path}"
            for method, path in documented
            if (method, path) not in registered
        )
        assert not stale, f"skill documents routes with no registered handler: {stale}"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class TestEvents:
    def test_list_events(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.list_events.return_value = [
            CalendarEvent(
                uid="evt-1",
                summary="Meeting",
                description="Team meeting",
                location="Office",
                dtstart="2026-01-01T10:00:00",
                dtend="2026-01-01T11:00:00",
                calendar_id="cal1",
            )
        ]
        response = client.get(
            "/events", params={"start": "2026-01-01", "end": "2026-01-02"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["uid"] == "evt-1"
        assert data[0]["summary"] == "Meeting"
        mock_client.list_events.assert_called_once_with("2026-01-01", "2026-01-02", "")

    def test_list_events_with_calendar_id(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.list_events.return_value = []
        response = client.get(
            "/events",
            params={"start": "2026-01-01", "end": "2026-01-02", "calendar_id": "work"},
        )
        assert response.status_code == 200
        mock_client.list_events.assert_called_once_with(
            "2026-01-01", "2026-01-02", "work"
        )

    def test_create_event(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.create_event.return_value = CalendarEvent(
            uid="new-uid",
            summary="New Event",
            description="",
            location="",
            dtstart="2026-01-01T10:00:00",
            dtend="2026-01-01T11:00:00",
            calendar_id="",
        )
        response = client.post(
            "/events",
            json={
                "summary": "New Event",
                "dtstart": "2026-01-01T10:00:00",
                "dtend": "2026-01-01T11:00:00",
            },
        )
        assert response.status_code == 201
        assert response.json()["uid"] == "new-uid"

    def test_update_event(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.update_event.return_value = CalendarEvent(
            uid="evt-1",
            summary="Updated",
            description="",
            location="",
            dtstart="2026-01-01T10:00:00",
            dtend="2026-01-01T11:00:00",
            calendar_id="",
        )
        response = client.put(
            "/events/evt-1",
            json={
                "summary": "Updated",
                "dtstart": "2026-01-01T10:00:00",
                "dtend": "2026-01-01T11:00:00",
            },
        )
        assert response.status_code == 200
        assert response.json()["summary"] == "Updated"

    def test_delete_event(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.delete_event.return_value = None
        response = client.delete("/events/evt-1")
        assert response.status_code == 204
        mock_client.delete_event.assert_called_once_with("evt-1", "")

    def test_delete_event_not_found(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.delete_event.side_effect = NotFoundError("not found")
        response = client.delete("/events/evt-1")
        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "not_found"


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TestTasks:
    def test_list_tasks(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.list_tasks.return_value = [
            Task(
                uid="task-1",
                summary="Do something",
                description="",
                dtstart="",
                due="2026-01-01",
                status="NEEDS-ACTION",
                calendar_id="cal1",
            )
        ]
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["uid"] == "task-1"
        assert data[0]["status"] == "NEEDS-ACTION"

    def test_create_task(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.create_task.return_value = Task(
            uid="new-task",
            summary="New Task",
            description="",
            dtstart="",
            due="",
            status="",
            calendar_id="",
        )
        response = client.post("/tasks", json={"summary": "New Task"})
        assert response.status_code == 201
        assert response.json()["uid"] == "new-task"

    def test_update_task(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.update_task.return_value = Task(
            uid="task-1",
            summary="Updated Task",
            description="",
            dtstart="",
            due="",
            status="",
            calendar_id="",
        )
        response = client.put("/tasks/task-1", json={"summary": "Updated Task"})
        assert response.status_code == 200
        assert response.json()["summary"] == "Updated Task"

    def test_delete_task(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.delete_task.return_value = None
        response = client.delete("/tasks/task-1")
        assert response.status_code == 204
        mock_client.delete_task.assert_called_once_with("task-1", "")

    def test_delete_task_not_found(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.delete_task.side_effect = NotFoundError("not found")
        response = client.delete("/tasks/task-1")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


class TestContacts:
    def test_list_contacts(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.list_contacts.return_value = [
            Contact(
                uid="contact-1",
                full_name="John Doe",
                email="john@example.com",
                phone="555-1234",
                address="123 Main St",
                addressbook_id="ab1",
            )
        ]
        response = client.get("/contacts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["uid"] == "contact-1"
        assert data[0]["full_name"] == "John Doe"

    def test_create_contact(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.create_contact.return_value = Contact(
            uid="new-contact",
            full_name="Jane Doe",
            email="",
            phone="",
            address="",
            addressbook_id="",
        )
        response = client.post("/contacts", json={"full_name": "Jane Doe"})
        assert response.status_code == 201
        assert response.json()["uid"] == "new-contact"

    def test_update_contact(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.update_contact.return_value = Contact(
            uid="contact-1",
            full_name="Updated Name",
            email="",
            phone="",
            address="",
            addressbook_id="",
        )
        response = client.put("/contacts/contact-1", json={"full_name": "Updated Name"})
        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Name"

    def test_delete_contact(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.delete_contact.return_value = None
        response = client.delete("/contacts/contact-1")
        assert response.status_code == 204
        mock_client.delete_contact.assert_called_once_with("contact-1", "")

    def test_delete_contact_not_found(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.delete_contact.side_effect = NotFoundError("not found")
        response = client.delete("/contacts/contact-1")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------


class TestCalendars:
    def test_list_calendars(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.list_calendars.return_value = ["Personal", "Work"]
        response = client.get("/calendars")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Personal"
        assert data[1]["name"] == "Work"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


class TestErrorMapping:
    def test_auth_error_returns_401(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.list_events.side_effect = AuthError("bad creds")
        response = client.get(
            "/events", params={"start": "2026-01-01", "end": "2026-01-02"}
        )
        assert response.status_code == 401
        assert response.json()["code"] == "auth_failed"

    def test_conflict_error_returns_409(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.update_event.side_effect = ConflictError("etag mismatch")
        response = client.put(
            "/events/evt-1",
            json={
                "summary": "X",
                "dtstart": "2026-01-01T10:00:00",
                "dtend": "2026-01-01T11:00:00",
            },
        )
        assert response.status_code == 409

    def test_rate_limit_error_returns_429(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.list_tasks.side_effect = RateLimitError("slow down")
        response = client.get("/tasks")
        assert response.status_code == 429

    def test_caldav_error_returns_502(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.list_contacts.side_effect = CalDAVError("server down")
        response = client.get("/contacts")
        assert response.status_code == 502

    def test_agent_logic_error_returns_400(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.list_tasks.side_effect = AgentLogicError("missing uid")
        response = client.get("/tasks")
        assert response.status_code == 400

    def test_generic_calendar_error_returns_500(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        from robotsix_calendar.caldav_client.exceptions import CalendarError

        mock_client.list_calendars.side_effect = CalendarError("unexpected")
        response = client.get("/calendars")
        assert response.status_code == 500
