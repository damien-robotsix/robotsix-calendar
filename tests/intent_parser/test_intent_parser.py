"""Tests for IntentParser — llmio model calls mocked."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock robotsix_llmio in sys.modules
# ---------------------------------------------------------------------------

_mock_llmio_core = MagicMock()
sys.modules["robotsix_llmio.core"] = _mock_llmio_core

from robotsix_calendar.intent_parser import (  # noqa: E402
    CalendarOperation,
    ContactOperation,
    IntentParseError,
    IntentParser,
    ParsedIntent,
    TaskOperation,
    _build_system_prompt,
    _IntentOutput,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_run_agent(
    operation: str, params: dict[str, Any] | None = None
) -> _IntentOutput:
    """Return a mock intent output."""
    return _IntentOutput(operation=operation, params=params or {})  # type: ignore[arg-type]


def _setup_llmio_mock(output: _IntentOutput | Exception) -> MagicMock:
    """Set up llmio mocks: build_agent_for_level + run_agent return the given output."""
    mock_handle = MagicMock()
    _mock_llmio_core.build_agent_for_level.return_value = mock_handle

    if isinstance(output, Exception):
        _mock_llmio_core.run_agent.side_effect = output
    else:
        _mock_llmio_core.run_agent.return_value = output

    return mock_handle


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParse:
    @pytest.mark.parametrize(
        "instruction,expected_op,expected_params",
        [
            (
                "list events this week",
                CalendarOperation.LIST_EVENTS,
                {"start": "2026-06-15T00:00:00", "end": "2026-06-21T23:59:59"},
            ),
            (
                "add a dentist appointment next Tuesday at 3pm",
                CalendarOperation.CREATE_EVENT,
                {
                    "summary": "dentist appointment",
                    "dtstart": "2026-06-23T15:00:00",
                    "dtend": "2026-06-23T16:00:00",
                },
            ),
            (
                "reschedule the dentist to 4pm",
                CalendarOperation.UPDATE_EVENT,
                {"uid": "", "dtstart": "2026-06-23T16:00:00"},
            ),
            (
                "cancel the dentist appointment",
                CalendarOperation.DELETE_EVENT,
                {"uid": ""},
            ),
            (
                "show all contacts",
                ContactOperation.LIST_CONTACTS,
                {},
            ),
            (
                "add John Doe, john@example.com",
                ContactOperation.CREATE_CONTACT,
                {
                    "full_name": "John Doe",
                    "email": "john@example.com",
                },
            ),
            (
                "change John's email to john.doe@example.com",
                ContactOperation.UPDATE_CONTACT,
                {
                    "uid": "",
                    "email": "john.doe@example.com",
                },
            ),
            (
                "remove John Doe from contacts",
                ContactOperation.DELETE_CONTACT,
                {"uid": ""},
            ),
            (
                "Show me my pending tasks",
                TaskOperation.LIST_TASKS,
                {},
            ),
            (
                "what calendars do I have",
                CalendarOperation.LIST_CALENDARS,
                {},
            ),
            (
                "add a task: buy groceries by Friday",
                TaskOperation.CREATE_TASK,
                {"summary": "buy groceries", "due": "2026-06-26T23:59:59"},
            ),
            (
                "mark the buy groceries task as completed",
                TaskOperation.UPDATE_TASK,
                {"uid": "", "status": "COMPLETED"},
            ),
            (
                "remove the buy groceries task",
                TaskOperation.DELETE_TASK,
                {"uid": ""},
            ),
        ],
    )
    def test_classifies_operation(
        self,
        instruction: str,
        expected_op: CalendarOperation | ContactOperation | TaskOperation,
        expected_params: dict[str, Any],
    ) -> None:
        """Verify all 10 operation types are classified correctly."""
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        _setup_llmio_mock(_mock_run_agent(str(expected_op), expected_params))

        parser = IntentParser()
        result = parser.parse(instruction)

        assert isinstance(result, ParsedIntent)
        assert result.operation == expected_op
        for key, value in expected_params.items():
            assert result.params.get(key) == value
        assert result.original_text == instruction


class TestBuildAgentContract:
    """Guard the build_agent call signature against regressions."""

    def test_build_agent_called_with_level_2_and_raw_output_type(self) -> None:
        """build_agent_for_level must receive level=2 and the raw _IntentOutput class.

        The new robotsix-llmio wraps raw pydantic output_type in PromptedOutput
        on reasoning tiers, avoiding the tool_choice/thinking conflict.  If
        level regresses to 1 (Flash, no reasoning wrapping) or output_type is
        pre-wrapped, this guard catches it.
        """
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        _setup_llmio_mock(_mock_run_agent("list_events", {}))

        parser = IntentParser()
        parser.parse("list events")

        build_call = _mock_llmio_core.build_agent_for_level.call_args
        assert build_call is not None, "build_agent_for_level was never called"
        # First positional argument is the level
        assert build_call.args[0] == 2, (
            "IntentParser must call build_agent_for_level(2, ...); got "
            f"{build_call.args[0]!r}"
        )
        assert build_call.kwargs.get("output_type") is _IntentOutput, (
            "output_type must be the raw _IntentOutput class — "
            "llmio wraps it internally. "
            f"Got: {build_call.kwargs.get('output_type')!r}"
        )


class TestSystemPrompt:
    """Smoke-test the system prompt includes required operations."""

    def test_prompt_includes_list_calendars(self) -> None:
        prompt = _build_system_prompt()

        assert "list_calendars" in prompt
        assert "Calendar names can be obtained via list_calendars" in prompt

    def test_prompt_includes_current_date(self) -> None:
        """System prompt must inject the current UTC date for relative-date parsing."""
        from datetime import UTC, datetime

        prompt = _build_system_prompt()
        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

        assert f"Today's date is {today} (UTC)" in prompt

    def test_prompt_includes_task_ops(self) -> None:
        prompt = _build_system_prompt()

        assert "create_task" in prompt
        assert "update_task" in prompt
        assert "delete_task" in prompt

    @pytest.mark.parametrize(
        "op",
        [*CalendarOperation, *ContactOperation, *TaskOperation],
        ids=lambda op: op.value,
    )
    def test_system_prompt_mentions_every_operation(self, op: object) -> None:
        """Every enum value must appear in the system prompt so the LLM can emit it."""
        prompt = _build_system_prompt()
        assert op.value in prompt, (  # type: ignore[union-attr]
            f"Operation {op.value!r} is missing from the system prompt — "
            "the LLM will never be told it exists."
        )

    def test_calendar_operation_has_list_calendars(self) -> None:
        assert hasattr(CalendarOperation, "LIST_CALENDARS")
        assert CalendarOperation.LIST_CALENDARS == "list_calendars"  # type: ignore[comparison-overlap]


class TestParseError:
    def test_raises_intent_parse_error_on_llmio_failure(self) -> None:
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        _setup_llmio_mock(RuntimeError("model unavailable"))

        parser = IntentParser()

        with pytest.raises(IntentParseError, match="Intent parsing failed"):
            parser.parse("list events")

    def test_runs_inner_callback_and_returns_output(self) -> None:
        """run_agent invokes the _run callback, exercising handle.run_sync."""
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        mock_handle = _setup_llmio_mock(_mock_run_agent("list_events", {}))

        # Make run_sync return an object with a .output attribute (pydantic-ai >=1).
        run_result = MagicMock()
        run_result.output = _IntentOutput(operation="list_events", params={})
        mock_handle.run_sync.return_value = run_result

        # Make run_agent actually call the supplied _run callback.
        def _call_run(_handle: object, run: object, **_kwargs: object) -> object:
            return run()  # type: ignore[operator]

        _mock_llmio_core.run_agent.side_effect = _call_run

        parser = IntentParser()
        result = parser.parse("list events this week")

        mock_handle.run_sync.assert_called_once_with("list events this week")
        assert result.operation == CalendarOperation.LIST_EVENTS

    def test_raises_on_unexpected_output_type(self) -> None:
        """A non-_IntentOutput result raises IntentParseError (re-raised cleanly)."""
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        _setup_llmio_mock(_mock_run_agent("list_events", {}))
        _mock_llmio_core.run_agent.return_value = {"not": "an output"}

        parser = IntentParser()

        with pytest.raises(IntentParseError, match="Unexpected output type"):
            parser.parse("list events")
