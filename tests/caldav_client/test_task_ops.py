"""Tests for task operations — listing, aggregation, conversion."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from robotsix_calendar.caldav_client import CalDavClient, Task
from tests.caldav_client.conftest import _mock_vtodo

# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestListTasks:
    def test_returns_list_of_tasks(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.search.return_value = [
            _mock_vtodo(uid="task-1"),
            _mock_vtodo(uid="task-2", summary="Second task"),
        ]

        result = client.list_tasks()

        assert len(result) == 2
        assert isinstance(result[0], Task)
        assert result[0].uid == "task-1"
        assert result[1].uid == "task-2"


class TestListTasksAggregation:
    def test_aggregates_across_all_calendars_when_calendar_id_empty(
        self, client: CalDavClient
    ) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.search.return_value = [_mock_vtodo(uid="task-a")]
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        cal_b.search.return_value = [
            _mock_vtodo(uid="task-b1"),
            _mock_vtodo(uid="task-b2"),
        ]
        cal_c = MagicMock(name="Damien")
        cal_c.name = "Damien"
        cal_c.search.return_value = []  # VTODO collections with no tasks
        client._principal.calendars.return_value = [cal_a, cal_b, cal_c]

        result = client.list_tasks()

        assert len(result) == 3
        assert result[0].uid == "task-a"
        assert result[0].calendar_id == "Robotsix"
        assert result[1].uid == "task-b1"
        assert result[1].calendar_id == "Birthdays"
        assert result[2].uid == "task-b2"
        assert result[2].calendar_id == "Birthdays"

    def test_single_calendar_when_id_provided(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.search.return_value = [_mock_vtodo(uid="task-a")]
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client.list_tasks(calendar_id="Robotsix")

        assert len(result) == 1
        assert result[0].uid == "task-a"
        cal_b.search.assert_not_called()


class TestToTask:
    def test_all_fields_parsed_from_ical(self) -> None:
        """VTODO fields map correctly via _to_task."""
        import datetime

        values: dict[str, Any] = {
            "UID": "task-1",
            "SUMMARY": "Buy milk",
            "DESCRIPTION": "Get 2%",
            "DTSTART": MagicMock(dt=datetime.datetime(2026, 6, 20, 8, 0, 0)),
            "DUE": MagicMock(dt=datetime.date(2026, 6, 21)),
            "STATUS": "NEEDS-ACTION",
        }
        comp = MagicMock()
        comp.get.side_effect = lambda name, default=None: values.get(name, default)
        obj = MagicMock()
        obj.icalendar_component = comp

        task = CalDavClient._to_task(obj, calendar_id="cal")

        assert task.uid == "task-1"
        assert task.summary == "Buy milk"
        assert task.description == "Get 2%"
        assert task.dtstart == "2026-06-20T08:00:00"
        assert task.due == "2026-06-21"
        assert task.status == "NEEDS-ACTION"
        assert task.calendar_id == "cal"

    def test_missing_fields_yield_empty(self) -> None:
        comp = MagicMock()
        comp.get.side_effect = lambda _name, default=None: default
        obj = MagicMock()
        obj.icalendar_component = comp

        task = CalDavClient._to_task(obj)

        assert task.uid == ""
        assert task.summary == ""
        assert task.description == ""
        assert task.dtstart == ""
        assert task.due == ""
        assert task.status == ""
        assert task.calendar_id == ""


# ---------------------------------------------------------------------------
# CreateTask
# ---------------------------------------------------------------------------


class TestCreateTask:
    def test_generates_uid_when_empty(self, client: CalDavClient) -> None:
        """When task.uid is empty, a UUID is generated and passed to save_todo."""
        cal = client._principal.calendars.return_value[0]
        saved_mock = _mock_vtodo(uid="server-uid", summary="My Task")
        cal.save_todo.return_value = saved_mock

        task = Task(summary="My Task", uid="")
        client.create_task(task)

        # The iCal string passed to save_todo must contain a generated UID
        ical: str = cal.save_todo.call_args[0][0]
        uid_line = next(line for line in ical.split("\n") if line.startswith("UID:"))
        generated_uid = uid_line[len("UID:") :]
        # A UUID4 is 36 chars (e.g. 550e8400-e29b-41d4-a716-446655440000)
        assert len(generated_uid) == 36
        assert generated_uid.count("-") == 4

    def test_calls_save_todo_with_vtodo(self, client: CalDavClient) -> None:
        """cal.save_todo is called with a VTODO iCal string containing task fields."""
        cal = client._principal.calendars.return_value[0]
        saved_mock = _mock_vtodo(uid="task-1", summary="Buy milk")
        cal.save_todo.return_value = saved_mock

        task = Task(
            uid="task-1", summary="Buy milk", description="2%", status="NEEDS-ACTION"
        )
        client.create_task(task)

        cal.save_todo.assert_called_once()
        ical: str = cal.save_todo.call_args[0][0]
        assert "BEGIN:VTODO" in ical
        assert "UID:task-1" in ical
        assert "SUMMARY:Buy milk" in ical
        assert "DESCRIPTION:2%" in ical
        assert "STATUS:NEEDS-ACTION" in ical
        assert "END:VTODO" in ical

    def test_returns_task_with_server_uid_and_calendar_id(
        self, client: CalDavClient
    ) -> None:
        """The returned Task carries the server-assigned uid and the calendar name."""
        cal = client._principal.calendars.return_value[0]
        cal.name = "MyCalendar"
        saved_mock = _mock_vtodo(uid="srv-uid-99", summary="Task X")
        cal.save_todo.return_value = saved_mock

        task = Task(uid="client-uid", summary="Task X")
        result = client.create_task(task)

        assert isinstance(result, Task)
        assert result.uid == "srv-uid-99"
        assert result.calendar_id == "MyCalendar"


# ---------------------------------------------------------------------------
# UpdateTask
# ---------------------------------------------------------------------------


class TestUpdateTask:
    def test_finds_task_by_uid_and_updates(self, client: CalDavClient) -> None:
        """When UID exists, update_task locates it and calls save_todo with new data."""
        cal = client._principal.calendars.return_value[0]
        cal.name = "CalA"
        existing_obj = _mock_vtodo(uid="task-1", summary="Old summary")
        cal.get_todo_by_uid.return_value = existing_obj
        saved_mock = _mock_vtodo(uid="task-1", summary="New summary")
        cal.save_todo.return_value = saved_mock

        updated_task = Task(summary="New summary", description="new desc")
        result = client.update_task("task-1", updated_task)

        cal.save_todo.assert_called_once()
        ical: str = cal.save_todo.call_args[0][0]
        assert "UID:task-1" in ical
        assert "SUMMARY:New summary" in ical
        assert result.uid == "task-1"
        assert result.calendar_id == "CalA"

    def test_raises_not_found_when_uid_missing(self, client: CalDavClient) -> None:
        """NotFoundError is raised when the UID doesn't exist in any calendar."""
        cal_a = MagicMock(name="CalA")
        cal_a.name = "CalA"
        cal_a.get_todo_by_uid.side_effect = client._caldav.lib.error.NotFoundError
        cal_b = MagicMock(name="CalB")
        cal_b.name = "CalB"
        cal_b.get_todo_by_uid.side_effect = client._caldav.lib.error.NotFoundError
        client._principal.calendars.return_value = [cal_a, cal_b]

        import pytest

        from robotsix_calendar.caldav_client.exceptions import NotFoundError

        with pytest.raises(NotFoundError, match="not found"):
            client.update_task("nonexistent", Task(summary="X"))

    def test_with_explicit_calendar_id(self, client: CalDavClient) -> None:
        """When calendar_id is provided, only that calendar is searched."""
        cal_target = MagicMock(name="TargetCal")
        cal_target.name = "TargetCal"
        existing_obj = _mock_vtodo(uid="task-1")
        cal_target.get_todo_by_uid.return_value = existing_obj
        saved_mock = _mock_vtodo(uid="task-1", summary="Updated")
        cal_target.save_todo.return_value = saved_mock
        client._principal.calendars.return_value = [cal_target]

        result = client.update_task(
            "task-1", Task(summary="Updated"), calendar_id="TargetCal"
        )

        cal_target.get_todo_by_uid.assert_called_once_with("task-1")
        cal_target.save_todo.assert_called_once()
        assert result.uid == "task-1"
        assert result.calendar_id == "TargetCal"


# ---------------------------------------------------------------------------
# DeleteTask
# ---------------------------------------------------------------------------


class TestDeleteTask:
    def test_deletes_task_when_found_by_uid(self, client: CalDavClient) -> None:
        """When UID exists, delete_task calls obj.delete() and returns None."""
        cal = client._principal.calendars.return_value[0]
        existing_obj = _mock_vtodo(uid="task-to-delete")
        cal.get_todo_by_uid.return_value = existing_obj

        result = client.delete_task("task-to-delete")

        existing_obj.delete.assert_called_once()
        assert result is None

    def test_returns_none_when_uid_not_found(self, client: CalDavClient) -> None:
        """delete_task returns None (idempotent) when UID absent from all calendars."""
        cal_a = MagicMock(name="CalA")
        cal_a.name = "CalA"
        cal_a.get_todo_by_uid.side_effect = client._caldav.lib.error.NotFoundError
        cal_b = MagicMock(name="CalB")
        cal_b.name = "CalB"
        cal_b.get_todo_by_uid.side_effect = client._caldav.lib.error.NotFoundError
        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client.delete_task("nonexistent")

        cal_a.get_todo_by_uid.assert_called_once_with("nonexistent")
        cal_b.get_todo_by_uid.assert_called_once_with("nonexistent")
        assert result is None

    def test_with_explicit_calendar_id(self, client: CalDavClient) -> None:
        """When calendar_id is provided, only that calendar is searched for deletion."""
        cal_target = MagicMock(name="TargetCal")
        cal_target.name = "TargetCal"
        existing_obj = _mock_vtodo(uid="task-1")
        cal_target.get_todo_by_uid.return_value = existing_obj
        client._principal.calendars.return_value = [cal_target]

        result = client.delete_task("task-1", calendar_id="TargetCal")

        existing_obj.delete.assert_called_once()
        assert result is None


# ---------------------------------------------------------------------------
# _task_to_ical
# ---------------------------------------------------------------------------


class TestTaskToIcal:
    def test_builds_valid_vtodo_ical_string(self, client: CalDavClient) -> None:
        """_task_to_ical produces a VTODO iCal string with all expected fields."""
        task = Task(
            uid="task-1",
            summary="Buy milk",
            description="Get 2%",
            dtstart="2026-06-20T08:00:00",
            due="2026-06-21",
            status="NEEDS-ACTION",
            calendar_id="cal",
        )

        ical = client._task_to_ical(task)

        assert "BEGIN:VCALENDAR" in ical
        assert "VERSION:2.0" in ical
        assert "PRODID:-//robotsix-calendar//EN" in ical
        assert "BEGIN:VTODO" in ical
        assert "UID:task-1" in ical
        assert "DTSTAMP:" in ical
        assert "SUMMARY:Buy milk" in ical
        assert "DESCRIPTION:Get 2%" in ical
        assert "STATUS:NEEDS-ACTION" in ical
        assert "END:VTODO" in ical
        assert "END:VCALENDAR" in ical
        assert "DTSTART" in ical
        assert "DUE" in ical

    def test_omits_empty_fields(self, client: CalDavClient) -> None:
        """DTSTART, DUE, and STATUS are omitted when empty."""
        task = Task(
            uid="task-2",
            summary="Simple task",
            description="",
            dtstart="",
            due="",
            status="",
            calendar_id="",
        )

        ical = client._task_to_ical(task)

        assert "DTSTART" not in ical
        assert "DUE" not in ical
        assert "STATUS" not in ical
        assert "UID:task-2" in ical
        assert "SUMMARY:Simple task" in ical


# ---------------------------------------------------------------------------
# _find_task_by_uid
# ---------------------------------------------------------------------------


class TestFindTaskByUid:
    def test_finds_task_by_uid_across_calendars(self, client: CalDavClient) -> None:
        """_find_task_by_uid locates a task by UID across all calendars."""
        cal_a = MagicMock(name="CalA")
        cal_a.name = "CalA"
        task_a2 = _mock_vtodo(uid="task-a2")
        cal_a.get_todo_by_uid.return_value = task_a2

        cal_b = MagicMock(name="CalB")
        cal_b.name = "CalB"

        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client._find_task_by_uid("task-a2")

        assert result is not None
        found_cal, found_obj = result
        assert found_cal is cal_a
        assert found_obj is task_a2

    def test_returns_none_when_not_found(self, client: CalDavClient) -> None:
        """_find_task_by_uid returns None when no calendar holds the UID."""
        cal_a = MagicMock(name="CalA")
        cal_a.name = "CalA"
        cal_a.get_todo_by_uid.side_effect = client._caldav.lib.error.NotFoundError
        cal_b = MagicMock(name="CalB")
        cal_b.name = "CalB"
        cal_b.get_todo_by_uid.side_effect = client._caldav.lib.error.NotFoundError
        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client._find_task_by_uid("nonexistent")

        assert result is None
