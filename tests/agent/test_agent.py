"""Tests for CalendarAgent — all external deps mocked."""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from robotsix_calendar_agent.settings import Settings

# Shared helpers live in conftest.


def _write_temp_config(overrides: dict | None = None) -> str:
    """Write a temporary config.json and return its path."""
    data: dict = {
        "RADICALE_URL": "https://radicale.example.com",
        "RADICALE_USERNAME": "user",
        "RADICALE_PASSWORD": "pass",  # pragma: allowlist secret
    }
    if overrides:
        data.update(overrides)
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_agent_config_")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCalendarAgentInit:
    def test_creates_with_config_file(self) -> None:
        config_path = _write_temp_config()
        os.environ["ROBOTSIX_CONFIG_FILE"] = config_path

        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
            patch("robotsix_config.load_config") as mock_load,
        ):
            mock_load.return_value = Settings(
                RADICALE_URL="https://x.com",
                RADICALE_USERNAME="u",
                RADICALE_PASSWORD="p",  # type: ignore[arg-type]  # pragma: allowlist secret
            )

            from robotsix_calendar_agent.agent import CalendarAgent

            agent = CalendarAgent()
            assert agent._agent_id == "calendar"

    def test_raises_value_error_for_missing_credentials(self) -> None:
        config_path = _write_temp_config(
            {
                "RADICALE_URL": "",
                "RADICALE_USERNAME": "",
                "RADICALE_PASSWORD": "",
            }
        )
        os.environ["ROBOTSIX_CONFIG_FILE"] = config_path

        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
            patch("robotsix_config.load_config") as mock_load,
        ):
            mock_load.return_value = Settings(
                RADICALE_URL="",
                RADICALE_USERNAME="",
                RADICALE_PASSWORD="",  # type: ignore[arg-type]  # pragma: allowlist secret
            )

            from robotsix_calendar_agent.agent import CalendarAgent

            with pytest.raises(ValueError, match="credentials"):
                CalendarAgent()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_context_manager(self, calendar_agent: MagicMock) -> None:
        with calendar_agent as ctx:
            assert ctx is calendar_agent


# ---------------------------------------------------------------------------
# Dispatch-enum consistency
# ---------------------------------------------------------------------------


class TestDispatchEnumSync:
    """Verify _DISPATCH keys stay in sync with all operation enums."""

    def test_dispatch_keys_match_enum_values(self) -> None:
        from robotsix_calendar_agent.agent import _DISPATCH
        from robotsix_calendar_agent.intent_parser import (
            CalendarOperation,
            ContactOperation,
            TaskOperation,
        )

        dispatch_keys = set(_DISPATCH)
        enum_values = (
            {m.value for m in CalendarOperation}
            | {m.value for m in ContactOperation}
            | {m.value for m in TaskOperation}
        )
        assert dispatch_keys == enum_values, (
            f"Mismatch: extra in dict={dispatch_keys - enum_values}, "
            f"missing={enum_values - dispatch_keys}"
        )


class TestDispatchNounVerbSync:
    """Verify _OPERATION_NOUN / _OPERATION_VERB cover every _DISPATCH key
    that can reach _render_reply (delete operations are exempt — they are
    handled by the ``deleted``-is-True branch)."""

    def test_noun_verb_dicts_cover_dispatch_keys(self) -> None:
        from robotsix_calendar_agent.agent import (
            _DISPATCH,
            _OPERATION_NOUN,
            _OPERATION_VERB,
        )

        dispatch_keys = set(_DISPATCH)
        noun_verb_keys = set(_OPERATION_NOUN) | set(_OPERATION_VERB)
        exempt = {"delete_event", "delete_contact", "delete_task"}

        missing = dispatch_keys - noun_verb_keys - exempt
        assert not missing, (
            f"_OPERATION_NOUN / _OPERATION_VERB missing entries for: {missing}"
        )


# ---------------------------------------------------------------------------
# _summarize_item unit tests
# ---------------------------------------------------------------------------


class TestSummarizeItem:
    def test_bare_string_passthrough(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        assert _summarize_item("hello") == "hello"  # type: ignore[arg-type]

    def test_task_with_due_and_status(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item(
            {
                "summary": "Buy milk",
                "due": "2026-06-21",
                "status": "NEEDS-ACTION",
                "uid": "t1",
            }
        )
        assert result == "Buy milk due 2026-06-21 [NEEDS-ACTION] [uid=t1]"

    def test_task_without_uid(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"due": "2026-06-21"})
        assert result == "(untitled) due 2026-06-21"

    def test_task_untitled_no_fields(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"due": "2026-06-21", "uid": "t2"})
        assert "(untitled)" in result
        assert "[uid=t2]" in result

    def test_event_with_summary_and_dtstart_and_location(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item(
            {
                "summary": "Lunch",
                "dtstart": "2026-01-02T12:00:00",
                "location": "Office",
                "uid": "e1",
            }
        )
        assert result == "Lunch at 2026-01-02T12:00:00 (Office) [uid=e1]"

    def test_event_without_uid(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"summary": "Meeting", "dtstart": "2026-07-01"})
        assert result == "Meeting at 2026-07-01"

    def test_event_without_dtstart_summary_fallback(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"summary": "No time event"})
        assert result == "No time event"

    def test_contact_with_name_and_email(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"full_name": "Jane Doe", "email": "jane@example.com"})
        assert result == "Jane Doe <jane@example.com>"

    def test_contact_without_email(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"full_name": "Jane Doe"})
        assert result == "Jane Doe"

    def test_contact_without_name(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"email": "anon@example.com"})
        assert result == "(no name) <anon@example.com>"

    def test_unknown_dict_fallback(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"color": "blue", "size": 3})
        # Should fall through to json.dumps
        assert "color" in result
        assert "blue" in result


# ---------------------------------------------------------------------------
# _render_reply unit tests
# ---------------------------------------------------------------------------


class TestRenderReply:
    def test_deleted_confirmation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("delete_event", {"deleted": True}) == (
            "Done — the item was deleted."
        )

    def test_empty_list_events(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_events", []) == "No events found."

    def test_empty_list_calendars(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_calendars", []) == "No calendars found."

    def test_empty_list_tasks(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_tasks", []) == "No tasks found."

    def test_empty_list_contacts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_contacts", []) == "No contacts found."

    def test_empty_list_unknown_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("frobnicate", []) == "No items found."

    def test_non_empty_list(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_events",
            [
                {"summary": "Lunch", "dtstart": "2026-01-02T12:00:00", "uid": "e1"},
                {"summary": "Dinner", "dtstart": "2026-01-02T19:00:00"},
            ],
        )
        assert result.startswith("Found 2:\n")
        assert "Lunch" in result
        assert "Dinner" in result
        assert "- " in result

    def test_dict_update_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "update_event", {"summary": "Updated meeting", "uid": "e1"}
        )
        assert result.startswith("Updated: ")

    def test_dict_create_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("create_event", {"summary": "New event", "uid": "e2"})
        assert result.startswith("Created: ")

    def test_dict_create_task_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("create_task", {"summary": "New task", "uid": "t2"})
        assert result.startswith("Created: ")

    def test_dict_other_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("delete_event", {"summary": "X"})
        assert result.startswith("Result: ")

    def test_fallback_non_dict_non_list(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_events", 42) == "42"
        assert _render_reply("list_events", "plain") == "plain"

    def test_list_with_calendar_strings(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("list_calendars", ["Robotsix", "Birthdays"])
        assert "Found 2" in result
        assert "Robotsix" in result
        assert "Birthdays" in result

    def test_list_with_contact_dicts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_contacts",
            [{"full_name": "John Doe", "email": "j@x.com"}, {"full_name": "Jane"}],
        )
        assert "Found 2" in result
        assert "John Doe" in result
        assert "Jane" in result

    def test_list_with_task_dicts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_tasks",
            [
                {
                    "summary": "Buy milk",
                    "due": "2026-06-21",
                    "status": "NEEDS-ACTION",
                    "uid": "t1",
                }
            ],
        )
        assert "Found 1" in result
        assert "Buy milk" in result

    def test_deleted_not_true_is_not_deleted_branch(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        # {"deleted": False} should NOT match the deleted branch — falls to dict branch
        result = _render_reply("delete_event", {"deleted": False, "uid": "e1"})
        assert result != "Done — the item was deleted."
        assert "Result:" in result


# ---------------------------------------------------------------------------
# Dispatch-layer orchestration tests
# ---------------------------------------------------------------------------


class TestDispatch:
    """Verify that _dispatch routes each operation to the correct handler
    and calls the expected CalDavClient methods with the right arguments."""

    # -- unknown operation -------------------------------------------------

    def test_unknown_operation_raises_agent_logic_error(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.agent import AgentLogicError
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(operation="nonexistent_op", params={}, original_text="")
        with pytest.raises(AgentLogicError, match="Unknown operation"):
            calendar_agent._dispatch(parsed)

    # -- list operations ---------------------------------------------------

    def test_list_events_passes_params_to_client(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import CalendarEvent
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.list_events.return_value = [
            CalendarEvent(summary="Lunch", dtstart="2026-01-01", dtend="2026-01-01"),
        ]
        parsed = ParsedIntent(
            operation="list_events",
            params={"start": "2026-01-01", "end": "2026-01-31", "calendar_id": "cal1"},
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.list_events.assert_called_once_with(
            start="2026-01-01", end="2026-01-31", calendar_id="cal1"
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["summary"] == "Lunch"

    def test_list_tasks_passes_params_to_client(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import Task
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.list_tasks.return_value = [
            Task(summary="Buy milk", calendar_id="cal1"),
        ]
        parsed = ParsedIntent(
            operation="list_tasks",
            params={"calendar_id": "cal1"},
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.list_tasks.assert_called_once_with(calendar_id="cal1")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["summary"] == "Buy milk"

    def test_list_calendars_passes_params_to_client(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.list_calendars.return_value = ["Robotsix", "Birthdays"]
        parsed = ParsedIntent(operation="list_calendars", params={}, original_text="")
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.list_calendars.assert_called_once_with()
        assert result == ["Robotsix", "Birthdays"]

    def test_list_contacts_passes_params_to_client(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import Contact
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.list_contacts.return_value = [
            Contact(full_name="Jane Doe", addressbook_id="ab1"),
        ]
        parsed = ParsedIntent(
            operation="list_contacts",
            params={"addressbook_id": "ab1"},
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.list_contacts.assert_called_once_with(
            addressbook_id="ab1"
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["full_name"] == "Jane Doe"

    # -- create / update event ---------------------------------------------

    def test_create_event_calls_client_with_built_event(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import CalendarEvent
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.create_event.return_value = CalendarEvent(
            summary="Team standup",
            description="Daily",
            location="Room A",
            dtstart="2026-01-01T09:00:00",
            dtend="2026-01-01T09:15:00",
            calendar_id="cal1",
        )
        parsed = ParsedIntent(
            operation="create_event",
            params={
                "summary": "Team standup",
                "description": "Daily",
                "location": "Room A",
                "dtstart": "2026-01-01T09:00:00",
                "dtend": "2026-01-01T09:15:00",
                "calendar_id": "cal1",
            },
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.create_event.assert_called_once()
        call_args = calendar_agent._caldav.create_event.call_args
        built_event = call_args[0][0]
        assert isinstance(built_event, CalendarEvent)
        assert built_event.summary == "Team standup"
        assert built_event.calendar_id == "cal1"
        assert call_args[1] == {"calendar_id": "cal1"}

        assert isinstance(result, dict)
        assert result["summary"] == "Team standup"

    def test_update_event_calls_client_with_uid_and_built_event(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import CalendarEvent
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.update_event.return_value = CalendarEvent(
            summary="Team standup updated",
            dtstart="2026-01-02T09:00:00",
            dtend="2026-01-02T09:15:00",
            calendar_id="cal1",
        )
        parsed = ParsedIntent(
            operation="update_event",
            params={
                "uid": "evt-123",
                "summary": "Team standup updated",
                "dtstart": "2026-01-02T09:00:00",
                "dtend": "2026-01-02T09:15:00",
                "calendar_id": "cal1",
            },
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.update_event.assert_called_once()
        call_args = calendar_agent._caldav.update_event.call_args
        assert call_args[0][0] == "evt-123"  # uid is first positional arg
        built_event = call_args[0][1]
        assert isinstance(built_event, CalendarEvent)
        assert built_event.summary == "Team standup updated"
        assert call_args[1] == {"calendar_id": "cal1"}

        assert isinstance(result, dict)
        assert result["summary"] == "Team standup updated"

    def test_update_event_without_uid_raises_agent_logic_error(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.agent import AgentLogicError
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(
            operation="update_event",
            params={"summary": "No UID event"},
            original_text="",
        )
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            calendar_agent._dispatch(parsed)

    # -- delete event ------------------------------------------------------

    def test_delete_event_calls_client_with_uid(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(
            operation="delete_event",
            params={"uid": "evt-123", "calendar_id": "cal1"},
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.delete_event.assert_called_once_with(
            uid="evt-123", calendar_id="cal1"
        )
        assert result == {"deleted": True}

    def test_delete_event_without_uid_raises_agent_logic_error(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.agent import AgentLogicError
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(operation="delete_event", params={}, original_text="")
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            calendar_agent._dispatch(parsed)

    # -- create / update contact -------------------------------------------

    def test_create_contact_calls_client_with_built_contact(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import Contact
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.create_contact.return_value = Contact(
            full_name="Jane Doe",
            email="jane@example.com",
            phone="555-0100",
            address="123 Main St",
            addressbook_id="ab1",
        )
        parsed = ParsedIntent(
            operation="create_contact",
            params={
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "555-0100",
                "address": "123 Main St",
                "addressbook_id": "ab1",
            },
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.create_contact.assert_called_once()
        call_args = calendar_agent._caldav.create_contact.call_args
        built_contact = call_args[0][0]
        assert isinstance(built_contact, Contact)
        assert built_contact.full_name == "Jane Doe"
        assert built_contact.email == "jane@example.com"
        assert call_args[1] == {"addressbook_id": "ab1"}

        assert isinstance(result, dict)
        assert result["full_name"] == "Jane Doe"

    def test_update_contact_calls_client_with_uid_and_built_contact(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import Contact
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.update_contact.return_value = Contact(
            full_name="Jane Doe Updated", addressbook_id="ab1"
        )
        parsed = ParsedIntent(
            operation="update_contact",
            params={
                "uid": "cnt-456",
                "full_name": "Jane Doe Updated",
                "addressbook_id": "ab1",
            },
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.update_contact.assert_called_once()
        call_args = calendar_agent._caldav.update_contact.call_args
        assert call_args[0][0] == "cnt-456"  # uid is first positional arg
        built_contact = call_args[0][1]
        assert isinstance(built_contact, Contact)
        assert built_contact.full_name == "Jane Doe Updated"
        assert call_args[1] == {"addressbook_id": "ab1"}

        assert isinstance(result, dict)
        assert result["full_name"] == "Jane Doe Updated"

    def test_update_contact_without_uid_raises_agent_logic_error(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.agent import AgentLogicError
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(
            operation="update_contact",
            params={"full_name": "No UID contact"},
            original_text="",
        )
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            calendar_agent._dispatch(parsed)

    # -- delete contact ----------------------------------------------------

    def test_delete_contact_calls_client_with_uid(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(
            operation="delete_contact",
            params={"uid": "cnt-456", "addressbook_id": "ab1"},
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.delete_contact.assert_called_once_with(
            uid="cnt-456", addressbook_id="ab1"
        )
        assert result == {"deleted": True}

    def test_delete_contact_without_uid_raises_agent_logic_error(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.agent import AgentLogicError
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(operation="delete_contact", params={}, original_text="")
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            calendar_agent._dispatch(parsed)

    # -- create / update task ----------------------------------------------

    def test_create_task_calls_client_with_built_task(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import Task
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.create_task.return_value = Task(
            summary="Buy groceries",
            description="Get milk and eggs",
            due="2026-06-21",
            calendar_id="cal1",
        )
        parsed = ParsedIntent(
            operation="create_task",
            params={
                "summary": "Buy groceries",
                "description": "Get milk and eggs",
                "due": "2026-06-21",
                "calendar_id": "cal1",
            },
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.create_task.assert_called_once()
        call_args = calendar_agent._caldav.create_task.call_args
        built_task = call_args[0][0]
        assert isinstance(built_task, Task)
        assert built_task.summary == "Buy groceries"
        assert built_task.description == "Get milk and eggs"
        assert built_task.due == "2026-06-21"
        assert call_args[1] == {"calendar_id": "cal1"}

        assert isinstance(result, dict)
        assert result["summary"] == "Buy groceries"

    def test_update_task_calls_client_with_uid_and_built_task(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import Task
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        calendar_agent._caldav.update_task.return_value = Task(
            summary="Buy groceries updated",
            due="2026-06-22",
            calendar_id="cal1",
        )
        parsed = ParsedIntent(
            operation="update_task",
            params={
                "uid": "task-123",
                "summary": "Buy groceries updated",
                "due": "2026-06-22",
                "calendar_id": "cal1",
            },
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.update_task.assert_called_once()
        call_args = calendar_agent._caldav.update_task.call_args
        assert call_args[0][0] == "task-123"  # uid is first positional arg
        built_task = call_args[0][1]
        assert isinstance(built_task, Task)
        assert built_task.summary == "Buy groceries updated"
        assert call_args[1] == {"calendar_id": "cal1"}

        assert isinstance(result, dict)
        assert result["summary"] == "Buy groceries updated"

    def test_update_task_without_uid_raises_agent_logic_error(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.agent import AgentLogicError
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(
            operation="update_task",
            params={"summary": "No UID task"},
            original_text="",
        )
        with pytest.raises(AgentLogicError, match="UID is required to update"):
            calendar_agent._dispatch(parsed)

    # -- delete task -------------------------------------------------------

    def test_delete_task_calls_client_with_uid(self, calendar_agent: MagicMock) -> None:
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(
            operation="delete_task",
            params={"uid": "task-123", "calendar_id": "cal1"},
            original_text="",
        )
        result = calendar_agent._dispatch(parsed)

        calendar_agent._caldav.delete_task.assert_called_once_with(
            uid="task-123", calendar_id="cal1"
        )
        assert result == {"deleted": True}

    def test_delete_task_without_uid_raises_agent_logic_error(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.agent import AgentLogicError
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        parsed = ParsedIntent(operation="delete_task", params={}, original_text="")
        with pytest.raises(AgentLogicError, match="UID is required to delete"):
            calendar_agent._dispatch(parsed)

    # -- parametrized: all 10 operation strings route to correct handler ----

    @pytest.mark.parametrize(
        "operation,params,expected_client_method,expected_call_kwargs",
        [
            (
                "list_events",
                {"start": "2026-01-01", "end": "2026-01-31", "calendar_id": "cal1"},
                "list_events",
                {"start": "2026-01-01", "end": "2026-01-31", "calendar_id": "cal1"},
            ),
            (
                "list_tasks",
                {"calendar_id": "cal1"},
                "list_tasks",
                {"calendar_id": "cal1"},
            ),
            (
                "list_calendars",
                {},
                "list_calendars",
                {},
            ),
            (
                "list_contacts",
                {"addressbook_id": "ab1"},
                "list_contacts",
                {"addressbook_id": "ab1"},
            ),
            (
                "create_event",
                {"summary": "Test", "calendar_id": "cal1"},
                "create_event",
                None,  # special-cased below — checks positional CalendarEvent
            ),
            (
                "update_event",
                {"uid": "evt-1", "summary": "Test", "calendar_id": "cal1"},
                "update_event",
                None,
            ),
            (
                "delete_event",
                {"uid": "evt-1", "calendar_id": "cal1"},
                "delete_event",
                {"uid": "evt-1", "calendar_id": "cal1"},
            ),
            (
                "create_contact",
                {"full_name": "Jane", "addressbook_id": "ab1"},
                "create_contact",
                None,
            ),
            (
                "update_contact",
                {"uid": "cnt-1", "full_name": "Jane", "addressbook_id": "ab1"},
                "update_contact",
                None,
            ),
            (
                "delete_contact",
                {"uid": "cnt-1", "addressbook_id": "ab1"},
                "delete_contact",
                {"uid": "cnt-1", "addressbook_id": "ab1"},
            ),
            (
                "create_task",
                {"summary": "Buy milk", "calendar_id": "cal1"},
                "create_task",
                None,
            ),
            (
                "update_task",
                {"uid": "task-1", "summary": "Buy milk", "calendar_id": "cal1"},
                "update_task",
                None,
            ),
            (
                "delete_task",
                {"uid": "task-1", "calendar_id": "cal1"},
                "delete_task",
                {"uid": "task-1", "calendar_id": "cal1"},
            ),
        ],
    )
    def test_dispatch_routes_to_correct_handler(
        self,
        calendar_agent: MagicMock,
        operation: str,
        params: dict[str, object],
        expected_client_method: str,
        expected_call_kwargs: dict[str, object] | None,
    ) -> None:
        """Every known operation string reaches the correct CalDavClient method."""
        from robotsix_calendar_agent.caldav_client import (
            CalendarEvent,
            Contact,
            Task,
        )
        from robotsix_calendar_agent.intent_parser import ParsedIntent

        # Set up mock returns so handlers can serialize results.
        mock = calendar_agent._caldav
        if operation in ("list_events", "create_event", "update_event"):
            mock.list_events.return_value = []
            mock.create_event.return_value = CalendarEvent(
                summary="x", dtstart="2026-01-01", dtend="2026-01-01"
            )
            mock.update_event.return_value = CalendarEvent(
                summary="x", dtstart="2026-01-01", dtend="2026-01-01"
            )
        elif operation in ("list_contacts", "create_contact", "update_contact"):
            mock.list_contacts.return_value = []
            mock.create_contact.return_value = Contact(full_name="x")
            mock.update_contact.return_value = Contact(full_name="x")
        elif operation == "list_tasks":
            mock.list_tasks.return_value = []
        elif operation == "list_calendars":
            mock.list_calendars.return_value = []
        elif operation in ("create_task", "update_task"):
            mock.create_task.return_value = Task(summary="x")
            mock.update_task.return_value = Task(summary="x")

        parsed = ParsedIntent(operation=operation, params=params, original_text="")
        calendar_agent._dispatch(parsed)

        client_method = getattr(calendar_agent._caldav, expected_client_method)
        assert client_method.called, (
            f"Expected {expected_client_method} to be called for {operation}, "
            f"but it was not."
        )

        if expected_call_kwargs is not None:
            client_method.assert_called_once_with(**expected_call_kwargs)
        else:
            # create/update handlers pass domain object as positional arg;
            # just verify the call happened (detailed asserts are in the
            # dedicated per-operation tests above).
            assert client_method.call_count >= 1
