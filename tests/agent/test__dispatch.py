"""Dedicated unit tests for agent/_dispatch.py helpers.

Covers _build_event, _build_task, _build_contact, _entity_op,
_delete_entity_op, and the per-operation _handle_* functions without
requiring a CalendarAgent instance or config.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from robotsix_calendar_agent.agent._dispatch import (
    _build_contact,
    _build_event,
    _build_task,
    _delete_entity_op,
    _entity_op,
    _handle_create_or_update_contact,
    _handle_create_or_update_event,
    _handle_create_or_update_task,
    _handle_delete_contact,
    _handle_delete_event,
    _handle_delete_task,
    _handle_list_calendars,
    _handle_list_contacts,
    _handle_list_events,
    _handle_list_tasks,
)
from robotsix_calendar_agent.caldav_client import CalendarEvent, Contact, Task
from robotsix_calendar_agent.caldav_client.exceptions import AgentLogicError

# ---------------------------------------------------------------------------
# _build_event
# ---------------------------------------------------------------------------


class TestBuildEvent:
    def test_all_fields_provided(self) -> None:
        params = {
            "summary": "Standup",
            "description": "Daily sync",
            "location": "Room A",
            "dtstart": "2026-01-01T09:00:00",
            "dtend": "2026-01-01T09:15:00",
            "calendar_id": "cal1",
        }
        event = _build_event(params)
        assert isinstance(event, CalendarEvent)
        assert event.summary == "Standup"
        assert event.description == "Daily sync"
        assert event.location == "Room A"
        assert event.dtstart == "2026-01-01T09:00:00"
        assert event.dtend == "2026-01-01T09:15:00"
        assert event.calendar_id == "cal1"

    def test_minimal_params_fills_defaults(self) -> None:
        params = {
            "summary": "Meeting",
            "dtstart": "2026-06-01",
            "dtend": "2026-06-01",
        }
        event = _build_event(params)
        assert event.summary == "Meeting"
        assert event.description == ""
        assert event.location == ""
        assert event.calendar_id == ""

    def test_empty_dict_all_defaults(self) -> None:
        event = _build_event({})
        assert event.summary == ""
        assert event.description == ""
        assert event.location == ""
        assert event.dtstart == ""
        assert event.dtend == ""
        assert event.calendar_id == ""


# ---------------------------------------------------------------------------
# _build_task
# ---------------------------------------------------------------------------


class TestBuildTask:
    def test_all_fields_provided(self) -> None:
        params = {
            "summary": "Buy milk",
            "description": "Get 2%",
            "dtstart": "2026-06-20",
            "due": "2026-06-21",
            "status": "NEEDS-ACTION",
            "calendar_id": "cal1",
        }
        task = _build_task(params)
        assert isinstance(task, Task)
        assert task.summary == "Buy milk"
        assert task.description == "Get 2%"
        assert task.dtstart == "2026-06-20"
        assert task.due == "2026-06-21"
        assert task.status == "NEEDS-ACTION"
        assert task.calendar_id == "cal1"

    def test_minimal_params_fills_defaults(self) -> None:
        params = {"summary": "Buy milk"}
        task = _build_task(params)
        assert task.summary == "Buy milk"
        assert task.description == ""
        assert task.dtstart == ""
        assert task.due == ""
        assert task.status == ""
        assert task.calendar_id == ""

    def test_empty_dict_all_defaults(self) -> None:
        task = _build_task({})
        assert task.summary == ""
        assert task.description == ""
        assert task.dtstart == ""
        assert task.due == ""
        assert task.status == ""
        assert task.calendar_id == ""


# ---------------------------------------------------------------------------
# _build_contact
# ---------------------------------------------------------------------------


class TestBuildContact:
    def test_all_fields_provided(self) -> None:
        params = {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-0100",
            "address": "123 Main St",
            "addressbook_id": "ab1",
        }
        contact = _build_contact(params)
        assert isinstance(contact, Contact)
        assert contact.full_name == "Jane Doe"
        assert contact.email == "jane@example.com"
        assert contact.phone == "555-0100"
        assert contact.address == "123 Main St"
        assert contact.addressbook_id == "ab1"

    def test_minimal_params_fills_defaults(self) -> None:
        params = {"full_name": "Jane Doe"}
        contact = _build_contact(params)
        assert contact.full_name == "Jane Doe"
        assert contact.email == ""
        assert contact.phone == ""
        assert contact.address == ""
        assert contact.addressbook_id == ""

    def test_empty_dict_all_defaults(self) -> None:
        contact = _build_contact({})
        assert contact.full_name == ""
        assert contact.email == ""
        assert contact.phone == ""
        assert contact.address == ""
        assert contact.addressbook_id == ""


# ---------------------------------------------------------------------------
# _entity_op
# ---------------------------------------------------------------------------


class TestEntityOp:
    """Tests for the generic _entity_op helper covering create/update
    branching, id_key handling, and UID validation."""

    def _make_mocks(self):
        builder = MagicMock(return_value=MagicMock())
        serializer = MagicMock(return_value={"serialized": True})
        create_fn = MagicMock(return_value=MagicMock())
        update_fn = MagicMock(return_value=MagicMock())
        return builder, serializer, create_fn, update_fn

    # -- create path -------------------------------------------------------

    def test_create_when_operation_is_none(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
            operation=None,
        )
        create_fn.assert_called_once()
        update_fn.assert_not_called()
        serializer.assert_called_once()

    def test_create_when_operation_is_empty_string(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
            operation="",
        )
        create_fn.assert_called_once()
        update_fn.assert_not_called()

    def test_create_when_operation_does_not_start_with_update(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
            operation="frobnicate",
        )
        create_fn.assert_called_once()
        update_fn.assert_not_called()

    def test_create_passes_entity_and_id_key_kwarg(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test", "calendar_id": "cal1"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
        )
        create_fn.assert_called_once_with(builder.return_value, calendar_id="cal1")

    def test_create_with_id_key_missing_from_params(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
        )
        create_fn.assert_called_once_with(builder.return_value, calendar_id="")

    def test_create_with_id_key_empty_in_params(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test", "calendar_id": ""},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
        )
        create_fn.assert_called_once_with(builder.return_value, calendar_id="")

    # -- update path -------------------------------------------------------

    def test_update_calls_update_fn_with_uid_and_id_key(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test", "uid": "evt-1", "calendar_id": "cal1"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
            operation="update",
        )
        update_fn.assert_called_once_with(
            "evt-1", builder.return_value, calendar_id="cal1"
        )
        create_fn.assert_not_called()
        serializer.assert_called_once()

    def test_update_with_operation_update_event_string(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test", "uid": "evt-2", "calendar_id": "cal2"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
            operation="update_event",
        )
        update_fn.assert_called_once_with(
            "evt-2", builder.return_value, calendar_id="cal2"
        )
        create_fn.assert_not_called()

    def test_update_with_id_key_missing_from_params(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        _entity_op(
            {"summary": "Test", "uid": "evt-3"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
            operation="update",
        )
        update_fn.assert_called_once_with("evt-3", builder.return_value, calendar_id="")

    # -- update missing / empty UID ----------------------------------------

    def test_update_with_missing_uid_raises_agent_logic_error(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            _entity_op(
                {"summary": "No UID"},
                builder=builder,
                serializer=serializer,
                create_fn=create_fn,
                update_fn=update_fn,
                id_key="calendar_id",
                operation="update",
            )
        create_fn.assert_not_called()
        update_fn.assert_not_called()

    def test_update_with_empty_uid_raises_agent_logic_error(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            _entity_op(
                {"summary": "Empty UID", "uid": ""},
                builder=builder,
                serializer=serializer,
                create_fn=create_fn,
                update_fn=update_fn,
                id_key="calendar_id",
                operation="update",
            )
        create_fn.assert_not_called()
        update_fn.assert_not_called()

    def test_update_with_uid_blank_but_present_key_raises(self) -> None:
        """uid key is present in params but its value is empty/blank."""
        builder, serializer, create_fn, update_fn = self._make_mocks()
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            _entity_op(
                {"uid": "", "summary": "Test"},
                builder=builder,
                serializer=serializer,
                create_fn=create_fn,
                update_fn=update_fn,
                id_key="calendar_id",
                operation="update",
            )

    # -- serializer return value -------------------------------------------

    def test_returns_serialized_result(self) -> None:
        builder, serializer, create_fn, update_fn = self._make_mocks()
        serializer.return_value = {"a": 1, "b": 2}
        result = _entity_op(
            {"summary": "Test"},
            builder=builder,
            serializer=serializer,
            create_fn=create_fn,
            update_fn=update_fn,
            id_key="calendar_id",
        )
        assert result == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# _delete_entity_op
# ---------------------------------------------------------------------------


class TestDeleteEntityOp:
    def test_happy_path_calls_delete_fn_and_returns_deleted_true(self) -> None:
        delete_fn = MagicMock()
        result = _delete_entity_op(
            {"uid": "evt-1", "calendar_id": "cal1"},
            delete_fn=delete_fn,
            id_key="calendar_id",
        )
        delete_fn.assert_called_once_with(uid="evt-1", calendar_id="cal1")
        assert result == {"deleted": True}

    def test_missing_uid_raises_agent_logic_error(self) -> None:
        delete_fn = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            _delete_entity_op(
                {"calendar_id": "cal1"},
                delete_fn=delete_fn,
                id_key="calendar_id",
            )
        delete_fn.assert_not_called()

    def test_empty_uid_raises_agent_logic_error(self) -> None:
        delete_fn = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            _delete_entity_op(
                {"uid": ""},
                delete_fn=delete_fn,
                id_key="calendar_id",
            )
        delete_fn.assert_not_called()

    def test_uid_blank_but_present_raises(self) -> None:
        """uid key is present but value is empty/blank."""
        delete_fn = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            _delete_entity_op(
                {"uid": "", "calendar_id": "cal1"},
                delete_fn=delete_fn,
                id_key="calendar_id",
            )
        delete_fn.assert_not_called()

    def test_id_key_missing_from_params_passes_empty_string(self) -> None:
        delete_fn = MagicMock()
        _delete_entity_op(
            {"uid": "evt-1"},
            delete_fn=delete_fn,
            id_key="addressbook_id",
        )
        delete_fn.assert_called_once_with(uid="evt-1", addressbook_id="")


# ---------------------------------------------------------------------------
# _handle_list_* and _handle_list_calendars
# ---------------------------------------------------------------------------


class TestHandleListEvents:
    def test_passes_params_and_serializes_to_dicts(self) -> None:
        client = MagicMock()
        client.list_events.return_value = [
            CalendarEvent(
                summary="Lunch",
                dtstart="2026-01-01T12:00:00",
                dtend="2026-01-01T13:00:00",
                calendar_id="cal1",
            ),
        ]
        result = _handle_list_events(
            client,
            {"start": "2026-01-01", "end": "2026-01-31", "calendar_id": "cal1"},
        )
        client.list_events.assert_called_once_with(
            start="2026-01-01", end="2026-01-31", calendar_id="cal1"
        )
        assert isinstance(result, list)
        assert result[0]["summary"] == "Lunch"
        assert result[0]["uid"] == ""

    def test_default_params_when_empty_dict(self) -> None:
        client = MagicMock()
        client.list_events.return_value = []
        _handle_list_events(client, {})
        client.list_events.assert_called_once_with(start="", end="", calendar_id="")


class TestHandleListTasks:
    def test_passes_params_and_serializes(self) -> None:
        client = MagicMock()
        client.list_tasks.return_value = [
            Task(summary="Buy milk", calendar_id="cal1"),
        ]
        result = _handle_list_tasks(client, {"calendar_id": "cal1"})
        client.list_tasks.assert_called_once_with(calendar_id="cal1")
        assert result[0]["summary"] == "Buy milk"

    def test_default_params_when_empty(self) -> None:
        client = MagicMock()
        client.list_tasks.return_value = []
        _handle_list_tasks(client, {})
        client.list_tasks.assert_called_once_with(calendar_id="")


class TestHandleListCalendars:
    def test_calls_client_and_returns_string_list(self) -> None:
        client = MagicMock()
        client.list_calendars.return_value = ["Robotsix", "Birthdays"]
        result = _handle_list_calendars(client, {})
        client.list_calendars.assert_called_once_with()
        assert result == ["Robotsix", "Birthdays"]


class TestHandleListContacts:
    def test_passes_params_and_serializes(self) -> None:
        client = MagicMock()
        client.list_contacts.return_value = [
            Contact(full_name="Jane Doe", addressbook_id="ab1"),
        ]
        result = _handle_list_contacts(client, {"addressbook_id": "ab1"})
        client.list_contacts.assert_called_once_with(addressbook_id="ab1")
        assert result[0]["full_name"] == "Jane Doe"

    def test_default_params_when_empty(self) -> None:
        client = MagicMock()
        client.list_contacts.return_value = []
        _handle_list_contacts(client, {})
        client.list_contacts.assert_called_once_with(addressbook_id="")


# ---------------------------------------------------------------------------
# _handle_create_or_update_* via the full handler (integration through
# _entity_op)
# ---------------------------------------------------------------------------


class TestHandleCreateOrUpdateEvent:
    def test_create_passes_to_client(self) -> None:
        client = MagicMock()
        client.create_event.return_value = CalendarEvent(
            summary="Standup",
            dtstart="2026-01-01T09:00:00",
            dtend="2026-01-01T09:15:00",
        )
        result = _handle_create_or_update_event(
            client,
            {
                "summary": "Standup",
                "dtstart": "2026-01-01T09:00:00",
                "dtend": "2026-01-01T09:15:00",
                "calendar_id": "cal1",
            },
            operation="create",
        )
        client.create_event.assert_called_once()
        assert result["summary"] == "Standup"

    def test_update_passes_uid_and_calls_update(self) -> None:
        client = MagicMock()
        client.update_event.return_value = CalendarEvent(
            summary="Updated",
            dtstart="2026-01-01T09:00:00",
            dtend="2026-01-01T09:15:00",
        )
        result = _handle_create_or_update_event(
            client,
            {"uid": "evt-1", "summary": "Updated", "calendar_id": "cal1"},
            operation="update",
        )
        client.update_event.assert_called_once()
        assert result["summary"] == "Updated"

    def test_update_without_uid_raises(self) -> None:
        client = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            _handle_create_or_update_event(
                client,
                {"summary": "No UID"},
                operation="update",
            )


class TestHandleDeleteEvent:
    def test_calls_client_delete(self) -> None:
        client = MagicMock()
        result = _handle_delete_event(client, {"uid": "evt-1", "calendar_id": "cal1"})
        client.delete_event.assert_called_once_with(uid="evt-1", calendar_id="cal1")
        assert result == {"deleted": True}

    def test_missing_uid_raises(self) -> None:
        client = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            _handle_delete_event(client, {"calendar_id": "cal1"})


class TestHandleCreateOrUpdateContact:
    def test_create_passes_to_client(self) -> None:
        client = MagicMock()
        client.create_contact.return_value = Contact(full_name="Jane Doe")
        result = _handle_create_or_update_contact(
            client,
            {"full_name": "Jane Doe", "addressbook_id": "ab1"},
            operation="create",
        )
        client.create_contact.assert_called_once()
        assert result["full_name"] == "Jane Doe"

    def test_update_without_uid_raises(self) -> None:
        client = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            _handle_create_or_update_contact(
                client,
                {"full_name": "No UID"},
                operation="update",
            )


class TestHandleDeleteContact:
    def test_calls_client_delete(self) -> None:
        client = MagicMock()
        result = _handle_delete_contact(
            client, {"uid": "cnt-1", "addressbook_id": "ab1"}
        )
        client.delete_contact.assert_called_once_with(uid="cnt-1", addressbook_id="ab1")
        assert result == {"deleted": True}

    def test_missing_uid_raises(self) -> None:
        client = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            _handle_delete_contact(client, {"addressbook_id": "ab1"})


class TestHandleCreateOrUpdateTask:
    def test_create_passes_to_client(self) -> None:
        client = MagicMock()
        client.create_task.return_value = Task(summary="Buy milk")
        result = _handle_create_or_update_task(
            client,
            {"summary": "Buy milk", "calendar_id": "cal1"},
            operation="create",
        )
        client.create_task.assert_called_once()
        assert result["summary"] == "Buy milk"

    def test_update_without_uid_raises(self) -> None:
        client = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            _handle_create_or_update_task(
                client,
                {"summary": "No UID"},
                operation="update",
            )


class TestHandleDeleteTask:
    def test_calls_client_delete(self) -> None:
        client = MagicMock()
        result = _handle_delete_task(client, {"uid": "task-1", "calendar_id": "cal1"})
        client.delete_task.assert_called_once_with(uid="task-1", calendar_id="cal1")
        assert result == {"deleted": True}

    def test_missing_uid_raises(self) -> None:
        client = MagicMock()
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            _handle_delete_task(client, {"calendar_id": "cal1"})
