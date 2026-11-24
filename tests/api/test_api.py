"""Tests for the FastAPI HTTP API endpoints."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from robotsix_http.fastapi import assert_chat_skill_route_parity

from robotsix_calendar.api import app
from robotsix_calendar.api._chat_skill import CHAT_SKILL_MARKDOWN
from robotsix_calendar.caldav_client._shared import (
    CalendarEvent,
    Contact,
    Task,
)
from robotsix_calendar.caldav_client.exceptions import (
    AgentLogicError,
    AuthError,
    CalDAVError,
    CalendarError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)


@pytest.fixture
def mock_client() -> Iterator[MagicMock]:
    """Create a mock CalDavClient and install it on ``app.state``.

    State-specific mock kept here (not in the shared ``client`` builder) so
    tests that do not exercise CalDAV-backed endpoints build a plain
    TestClient.
    """
    mock = MagicMock()
    app.state.caldav_client = mock
    yield mock
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

    def test_chat_skill_route_parity(self) -> None:
        """The descriptor and the app describe the same routes, both ways.

        Delegates to the shared
        :func:`robotsix_http.fastapi.assert_chat_skill_route_parity`, which
        fails if any registered route is undocumented or any documented
        route does not resolve.  ``/health`` and ``/chat-skill`` are ignored
        by default; the human-facing UI pages (``/``, ``/ui*``) are
        infrastructure the CRUD descriptor deliberately does not document.
        """
        assert_chat_skill_route_parity(
            app,
            CHAT_SKILL_MARKDOWN,
            ignore=("/", "/ui", "/ui/calendars", "/ui/events", "/ui/contacts"),
        )


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
        assert body["error"]["code"] == "not_found"


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
        mock_client.list_tasks.assert_called_once_with("", offset=0, limit=50)

    def test_list_tasks_pagination(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.list_tasks.return_value = []
        response = client.get("/tasks", params={"offset": 10, "limit": 5})
        assert response.status_code == 200
        mock_client.list_tasks.assert_called_once_with("", offset=10, limit=5)

    def test_list_tasks_invalid_limit(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        response = client.get("/tasks", params={"limit": 5000})
        assert response.status_code == 422
        mock_client.list_tasks.assert_not_called()

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
        mock_client.list_contacts.assert_called_once_with("", offset=0, limit=50)

    def test_list_contacts_pagination(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.list_contacts.return_value = []
        response = client.get("/contacts", params={"offset": 3, "limit": 2})
        assert response.status_code == 200
        mock_client.list_contacts.assert_called_once_with("", offset=3, limit=2)

    def test_list_contacts_invalid_offset(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        response = client.get("/contacts", params={"offset": -1})
        assert response.status_code == 422
        mock_client.list_contacts.assert_not_called()

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


class TestAddressbooks:
    def test_list_addressbooks(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.list_addressbooks.return_value = ["personal", "team"]
        response = client.get("/addressbooks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "personal"
        assert data[1]["name"] == "team"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


class TestErrorMapping:
    @pytest.mark.parametrize(
        ("exception", "expected_status", "expected_code", "expected_detail"),
        [
            pytest.param(
                AuthError("bad creds"),
                401,
                "auth_failed",
                "bad creds",
                id="auth_error",
            ),
            pytest.param(
                ConflictError("etag mismatch"),
                409,
                "conflict",
                "etag mismatch",
                id="conflict",
            ),
            pytest.param(
                RateLimitError("slow down"),
                429,
                "rate_limited",
                "slow down",
                id="rate_limited",
            ),
            pytest.param(
                CalDAVError("server down"),
                502,
                "caldav_error",
                "server down",
                id="caldav_error",
            ),
            pytest.param(
                AgentLogicError("missing uid"),
                400,
                "agent_logic_error",
                "missing uid",
                id="agent_logic_error",
            ),
            pytest.param(NotFoundError("not found"), 404, "not_found", "not found"),
            pytest.param(
                CalendarError("unexpected"),
                500,
                "calendar_error",
                "unexpected",
                id="calendar_error",
            ),
        ],
    )
    def test_calendar_error_renders_canonical_envelope(
        self,
        client: TestClient,
        mock_client: MagicMock,
        exception: CalendarError,
        expected_status: int,
        expected_code: str,
        expected_detail: str,
    ) -> None:
        """Assert the full canonical envelope for every CalendarError subclass.

        ``register_exception_handlers`` renders each subclass with its
        declared ``status_code``/``code`` (from ``exceptions.py``) and the
        human-readable message as ``detail``.  The ``expected_code`` schema
        check pins the table to the exception's static ``code`` attribute so
        the test cannot silently drift from the hierarchy it documents.
        """
        mock_client.list_events.side_effect = exception
        response = client.get(
            "/events", params={"start": "2026-01-01", "end": "2026-01-02"}
        )

        assert response.status_code == expected_status
        assert response.json() == {
            "error": {"code": expected_code, "detail": expected_detail}
        }
        # Schema check: the machine-readable code is the exception's own
        # static ``code``, so the table cannot drift from exceptions.py.
        assert expected_code == exception.code
