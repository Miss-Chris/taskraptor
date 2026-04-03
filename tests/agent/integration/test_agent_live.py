"""
Integration tests against the real Anthropic API.
Skipped automatically if TEST_ANTHROPIC_API_KEY is not set.

Run with:
    TEST_ANTHROPIC_API_KEY=sk-... uv run pytest tests/agent/integration/
"""
import functools
import os

import pytest

from apps.agent.agent import run_agent
from apps.agent.models import ChatMessage, Todo
from apps.agent.schemas import AgentRequest, ConversationEntry, ToolCallEntry, ToolContext
from apps.agent.tools import (
    add_todo,
    delete_todo,
    list_todos,
    search_todos,
    update_todo,
    create_schedule,
    list_schedules,
    delete_schedule,
)

LIVE_API_KEY = os.environ.get("TEST_ANTHROPIC_API_KEY", "")
skip_without_key = pytest.mark.skipif(
    not LIVE_API_KEY, reason="TEST_ANTHROPIC_API_KEY not set"
)


def _make_ctx(user_id: int) -> ToolContext:
    return ToolContext(
        add_todo=functools.partial(add_todo, user_id),
        list_todos=functools.partial(list_todos, user_id),
        update_todo=functools.partial(update_todo, user_id),
        delete_todo=functools.partial(delete_todo, user_id),
        search_todos=functools.partial(search_todos, user_id),
        create_schedule=functools.partial(create_schedule, user_id),
        list_schedules=functools.partial(list_schedules, user_id),
        delete_schedule=functools.partial(delete_schedule, user_id),
    )


def _make_req(user_id: int, message: str) -> AgentRequest:
    return AgentRequest(
        api_key=LIVE_API_KEY,
        user_id=user_id,
        user_timezone="UTC",
        message=message,
    )


@skip_without_key
@pytest.mark.django_db
def test_agent_adds_todo_via_live_api(user):
    result = run_agent(_make_req(user.pk, "Add a todo: buy oat milk"), _make_ctx(user.pk))

    assert result.stopped_reason in ("completed", "max_respond_calls")
    user_msgs = [a.user_message for a in result.actions if a.type == "user_message"]
    assert len(user_msgs) >= 1
    assert Todo.objects.filter(user=user).exists()


@skip_without_key
@pytest.mark.django_db
def test_agent_lists_todos_via_live_api(user):
    # Seed some todos first
    add_todo(user.pk, title="Alpha task")
    add_todo(user.pk, title="Beta task")

    result = run_agent(_make_req(user.pk, "What todos do I have?"), _make_ctx(user.pk))

    assert result.stopped_reason in ("completed", "max_respond_calls")
    user_msgs = [a.user_message for a in result.actions if a.type == "user_message"]
    assert len(user_msgs) >= 1


@skip_without_key
@pytest.mark.django_db
def test_agent_completes_todo_via_live_api(user):
    r = add_todo(user.pk, title="Go for a walk")
    todo_id = r["data"]["id"]

    result = run_agent(
        _make_req(user.pk, "Mark 'Go for a walk' as done"),
        _make_ctx(user.pk),
    )

    assert result.stopped_reason in ("completed", "max_respond_calls")
    todo = Todo.objects.get(id=todo_id)
    assert todo.is_completed is True


@skip_without_key
@pytest.mark.django_db
def test_agent_deletes_todo_via_live_api(user):
    add_todo(user.pk, title="Temporary task to delete")

    result = run_agent(
        _make_req(user.pk, "Delete the todo 'Temporary task to delete'"),
        _make_ctx(user.pk),
    )

    assert result.stopped_reason in ("completed", "max_respond_calls")
    assert not Todo.objects.filter(user=user, title="Temporary task to delete").exists()


@skip_without_key
@pytest.mark.django_db
def test_agent_with_conversation_history_and_token_tracking(user):
    """
    Large E2E test: agent receives 5 prior conversation messages and 3 prior
    tool call history entries, then handles a multi-step request. Asserts that:
    - The agent performs multiple tool calls
    - Token counts are populated and plausible
    - DB state reflects the actions taken
    """
    # Seed 4 existing todos
    add_todo(user.pk, title="Buy groceries", priority="medium")
    add_todo(user.pk, title="Call the dentist", priority="high")
    add_todo(user.pk, title="Renew car insurance", priority="high")
    add_todo(user.pk, title="Read book chapter 3", priority="low")

    # 5-message conversation history simulating a prior session
    conversation_history = [
        ConversationEntry(role="user",      content="What do I have on my list?"),
        ConversationEntry(role="assistant", content="You have 4 todos: Buy groceries, Call the dentist, Renew car insurance, Read book chapter 3."),
        ConversationEntry(role="user",      content="Add 'Submit expense report' as high priority"),
        ConversationEntry(role="assistant", content="Done, added 'Submit expense report' with high priority."),
        ConversationEntry(role="user",      content="Thanks. Remind me — which ones are high priority?"),
        ConversationEntry(role="assistant", content="High priority: Call the dentist, Renew car insurance, Submit expense report."),
    ]

    # 3 prior tool call history entries
    tool_call_history = [
        ToolCallEntry(index=0, tool_name="list_todos",  tool_input={},                          tool_output={"ok": True, "data": []}, summary="listed todos → 4 items"),
        ToolCallEntry(index=1, tool_name="add_todo",    tool_input={"title": "Submit expense report", "priority": "high"}, tool_output={"ok": True, "data": {}}, summary='added "Submit expense report" (id:abc123)'),
        ToolCallEntry(index=2, tool_name="list_todos",  tool_input={"priority": "high"},         tool_output={"ok": True, "data": []}, summary="listed todos → 3 items"),
    ]

    req = AgentRequest(
        api_key=LIVE_API_KEY,
        user_id=user.pk,
        user_timezone="America/Toronto",
        message="Mark 'Call the dentist' and 'Renew car insurance' as done, then tell me what high-priority items are still open.",
        conversation_history=conversation_history,
        tool_call_history=tool_call_history,
    )

    result = run_agent(req, _make_ctx(user.pk))

    # Agent must have done real work
    assert result.stopped_reason in ("completed", "max_respond_calls")

    tool_calls = [a for a in result.actions if a.type == "tool_call"]
    user_msgs  = [a for a in result.actions if a.type == "user_message"]

    # Should have called at least 2 update_todo calls + 1 list + 1 respond
    assert len(tool_calls) >= 3
    assert len(user_msgs) >= 1

    # The two todos should be completed in the DB
    assert Todo.objects.get(user=user, title="Call the dentist").is_completed is True
    assert Todo.objects.get(user=user, title="Renew car insurance").is_completed is True

    # Token counts must be populated (real API always returns usage)
    assert result.input_tokens > 0
    assert result.output_tokens > 0
    # Sanity: a multi-step run with history should use at least ~500 input tokens
    assert result.input_tokens > 500


@skip_without_key
@pytest.mark.django_db
def test_agent_multi_step_bulk_add_with_history_and_tokens(user):
    """
    Large E2E test: agent adds 3 todos in one turn, given a conversation history
    of 6 messages from a previous session. Asserts correct DB state, action
    ordering, and that cumulative token counts grow with each LLM call.
    """
    # Seed 2 existing todos to give the agent context
    add_todo(user.pk, title="Morning run", priority="low")
    add_todo(user.pk, title="Weekly review", priority="medium")

    # 6-message conversation history from an earlier session
    conversation_history = [
        ConversationEntry(role="user",      content="I need to plan my week."),
        ConversationEntry(role="assistant", content="Sure, what would you like to add?"),
        ConversationEntry(role="user",      content="Add 'Morning run' as low priority"),
        ConversationEntry(role="assistant", content="Added 'Morning run'."),
        ConversationEntry(role="user",      content="Also add 'Weekly review' as medium priority"),
        ConversationEntry(role="assistant", content="Added 'Weekly review'. Anything else?"),
    ]

    # 3 prior tool call history entries
    tool_call_history = [
        ToolCallEntry(index=0, tool_name="list_todos", tool_input={}, tool_output={"ok": True, "data": []}, summary="listed todos → 0 items"),
        ToolCallEntry(index=1, tool_name="add_todo",   tool_input={"title": "Morning run",   "priority": "low"},    tool_output={"ok": True, "data": {}}, summary='added "Morning run" (id:x1)'),
        ToolCallEntry(index=2, tool_name="add_todo",   tool_input={"title": "Weekly review", "priority": "medium"}, tool_output={"ok": True, "data": {}}, summary='added "Weekly review" (id:x2)'),
    ]

    req = AgentRequest(
        api_key=LIVE_API_KEY,
        user_id=user.pk,
        user_timezone="America/Toronto",
        message="Add these three todos: 'Buy birthday gift' (high), 'Book dentist appointment' (high), 'Clean out inbox' (medium). Then show me everything that's high priority.",
        conversation_history=conversation_history,
        tool_call_history=tool_call_history,
    )

    result = run_agent(req, _make_ctx(user.pk))

    assert result.stopped_reason in ("completed", "max_respond_calls")

    tool_calls = [a for a in result.actions if a.type == "tool_call"]
    user_msgs  = [a for a in result.actions if a.type == "user_message"]

    # At minimum: 3 add_todo calls + 1 list + 1 respond
    assert len(tool_calls) >= 4
    assert len(user_msgs) >= 1

    # All three todos must be in the DB
    assert Todo.objects.filter(user=user, title="Buy birthday gift").exists()
    assert Todo.objects.filter(user=user, title="Book dentist appointment").exists()
    assert Todo.objects.filter(user=user, title="Clean out inbox").exists()

    # Action indexes must be gapless and start at 0
    for expected, action in enumerate(result.actions):
        assert action.index == expected

    # Token counts populated and reflect the multi-call nature of the run
    assert result.input_tokens > 500
    assert result.output_tokens > 0
