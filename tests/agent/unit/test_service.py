"""
Unit tests for the service layer (apps/agent/service.py).
Uses a real DB but monkeypatches run_agent to avoid LLM calls.
"""
import pytest

from apps.agent.models import AgentRun, ChatMessage, ToolCall, UserProfile
from apps.agent.schemas import AgentAction, AgentResponse, ToolCallResult


def _fake_run_agent_factory(actions: list[AgentAction], stopped_reason: str = "completed"):
    """Returns a drop-in replacement for run_agent."""
    def fake_run_agent(request, tool_context, llm_client=None):
        return AgentResponse(actions=actions, stopped_reason=stopped_reason)
    return fake_run_agent


@pytest.mark.django_db
def test_handle_message_persists_agent_run(user, monkeypatch):
    from apps.agent import service

    monkeypatch.setattr(service, "run_agent", _fake_run_agent_factory([]))

    service.handle_message(user.pk, "hello", "cli")

    assert AgentRun.objects.filter(user=user).count() == 1
    run = AgentRun.objects.get(user=user)
    assert run.trigger_message == "hello"
    assert run.trigger_type == AgentRun.TriggerType.USER
    assert run.stopped_reason == "completed"


@pytest.mark.django_db
def test_handle_message_persists_tool_calls(user, monkeypatch):
    from apps.agent import service

    actions = [
        AgentAction(
            index=0,
            type="tool_call",
            tool_call=ToolCallResult(
                tool_name="add_todo",
                tool_input={"title": "Buy milk"},
                tool_output={"ok": True, "data": {"id": "abc"}},
                summary='added "Buy milk" (id:abc)',
            ),
        )
    ]
    monkeypatch.setattr(service, "run_agent", _fake_run_agent_factory(actions))

    service.handle_message(user.pk, "add buy milk", "cli")

    assert ToolCall.objects.filter(user=user, tool_name="add_todo").count() == 1
    tc = ToolCall.objects.get(user=user)
    assert tc.index == 0
    assert tc.tool_input == {"title": "Buy milk"}
    assert 'added "Buy milk"' in tc.summary


@pytest.mark.django_db
def test_handle_message_persists_chat_messages(user, monkeypatch):
    from apps.agent import service

    actions = [
        AgentAction(index=0, type="user_message", user_message="Done! Added your todo."),
    ]
    monkeypatch.setattr(service, "run_agent", _fake_run_agent_factory(actions))

    service.handle_message(user.pk, "add buy milk", "cli")

    messages = ChatMessage.objects.filter(user=user).order_by("created_at")
    # One user message + one assistant message
    assert messages.count() == 2
    assert messages.filter(role="assistant", content="Done! Added your todo.").exists()
    assert messages.filter(role="user", content="add buy milk").exists()


@pytest.mark.django_db
def test_handle_message_returns_user_messages(user, monkeypatch):
    from apps.agent import service

    actions = [
        AgentAction(index=0, type="user_message", user_message="First message."),
        AgentAction(
            index=1,
            type="tool_call",
            tool_call=ToolCallResult(
                tool_name="list_todos", tool_input={}, tool_output={"ok": True, "data": []}, summary="listed"
            ),
        ),
        AgentAction(index=2, type="user_message", user_message="Second message."),
    ]
    monkeypatch.setattr(service, "run_agent", _fake_run_agent_factory(actions))

    result = service.handle_message(user.pk, "list todos", "cli")

    assert result == ["First message.", "Second message."]


@pytest.mark.django_db
def test_handle_message_uses_profile_timezone(user, monkeypatch):
    from apps.agent import service

    captured = {}

    def fake_run_agent(request, tool_context, llm_client=None):
        captured["timezone"] = request.user_timezone
        return AgentResponse(actions=[], stopped_reason="completed")

    monkeypatch.setattr(service, "run_agent", fake_run_agent)

    # Profile was created with "America/New_York" in the fixture
    service.handle_message(user.pk, "hello", "cli")

    assert captured["timezone"] == "America/New_York"


@pytest.mark.django_db
def test_conversation_history_is_passed_to_agent(user, monkeypatch):
    """
    The most recent chat messages are included in the conversation_history
    passed to run_agent, in the correct order.
    """
    from apps.agent import service

    prior = [
        ("user",      "Add buy milk"),
        ("assistant", "Done, added 'Buy milk'."),
        ("user",      "Actually make it oat milk"),
        ("assistant", "Updated to 'Buy oat milk'."),
        ("user",      "Also add call dentist"),
        ("assistant", "Added 'Call dentist'."),
    ]
    for role, content in prior:
        ChatMessage.objects.create(
            user=user, role=role, content=content, channel="cli"
        )

    captured = {}

    def fake_run_agent(request, tool_context, llm_client=None):
        captured["history"] = request.conversation_history
        return AgentResponse(actions=[], stopped_reason="completed")

    monkeypatch.setattr(service, "run_agent", fake_run_agent)

    service.handle_message(user.pk, "what do I have?", "cli")

    history = captured["history"]
    assert len(history) == 6
    for i, (role, content) in enumerate(prior):
        assert history[i].role == role
        assert history[i].content == content


@pytest.mark.django_db
def test_tool_call_history_is_passed_to_agent(user, monkeypatch):
    """
    The most recent ToolCall records are included in the tool_call_history
    passed to run_agent, ordered oldest-first, with correct fields on each entry.
    """
    from apps.agent import service
    from apps.agent.models import AgentRun

    # Create an AgentRun to hang the tool calls off
    run = AgentRun.objects.create(
        user=user,
        trigger_message="seed run",
        trigger_type=AgentRun.TriggerType.USER,
        stopped_reason=AgentRun.StoppedReason.COMPLETED,
        model_used="claude-sonnet-4-5",
    )

    prior_calls = [
        (0, "add_todo",      {"title": "Buy milk"},        'added "Buy milk" (id:aaa)'),
        (1, "list_todos",    {},                           "listed todos → 1 items"),
        (2, "update_todo",   {"todo_id": "aaa"},           "updated aaa"),
        (3, "search_todos",  {"query": "milk"},            'searched "milk" → 1 items'),
        (4, "add_todo",      {"title": "Call dentist"},    'added "Call dentist" (id:bbb)'),
        (5, "delete_todo",   {"todo_id": "aaa"},           "deleted aaa"),
    ]
    for idx, tool_name, tool_input, summary in prior_calls:
        ToolCall.objects.create(
            user=user,
            agent_run=run,
            index=idx,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output={"ok": True},
            summary=summary,
        )

    captured = {}

    def fake_run_agent(request, tool_context, llm_client=None):
        captured["tool_history"] = request.tool_call_history
        return AgentResponse(actions=[], stopped_reason="completed")

    monkeypatch.setattr(service, "run_agent", fake_run_agent)

    service.handle_message(user.pk, "what's next?", "cli")

    tool_history = captured["tool_history"]
    assert len(tool_history) == 5
    expected_calls = prior_calls[-5:]
    for i, (idx, tool_name, tool_input, summary) in enumerate(expected_calls):
        assert tool_history[i].tool_name == tool_name
        assert tool_history[i].summary == summary
        assert tool_history[i].tool_input == tool_input


@pytest.mark.django_db
def test_conversation_history_is_trimmed_to_recent_messages(user, monkeypatch):
    from apps.agent import service

    for i in range(12):
        role = "user" if i % 2 == 0 else "assistant"
        ChatMessage.objects.create(
            user=user,
            role=role,
            content=f"message-{i}",
            channel="cli",
        )

    captured = {}

    def fake_run_agent(request, tool_context, llm_client=None):
        captured["history"] = request.conversation_history
        return AgentResponse(actions=[], stopped_reason="completed")

    monkeypatch.setattr(service, "run_agent", fake_run_agent)

    service.handle_message(user.pk, "latest?", "cli")

    history = captured["history"]
    assert len(history) == 8
    assert [entry.content for entry in history] == [f"message-{i}" for i in range(4, 12)]


@pytest.mark.django_db
def test_handle_message_defaults_to_utc_when_no_profile(db, monkeypatch):
    from apps.accounts.models import User
    from apps.agent import service

    # User with no profile
    u = User.objects.create_user(email="noprofile@example.com", password="pw!")

    captured = {}

    def fake_run_agent(request, tool_context, llm_client=None):
        captured["timezone"] = request.user_timezone
        return AgentResponse(actions=[], stopped_reason="completed")

    monkeypatch.setattr(service, "run_agent", fake_run_agent)

    service.handle_message(u.pk, "hello", "cli")

    assert captured["timezone"] == "UTC"
