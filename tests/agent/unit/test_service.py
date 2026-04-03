import pytest

from apps.agent.models import AgentRun, ChatMessage, ToolCall, UserProfile
from apps.agent.schemas import AgentAction, AgentResponse, ToolCallResult


def _fake_run_agent_factory(actions, stopped_reason="completed"):
    def fake_run_agent(request, tools, llm_client=None):
        return AgentResponse(
            actions=actions,
            stopped_reason=stopped_reason,
            input_tokens=123,
            output_tokens=45,
        )

    return fake_run_agent


@pytest.mark.django_db
def test_handle_message_persists_schedule_trigger(user, monkeypatch):
    from apps.agent import service

    monkeypatch.setattr(service, "run_agent", _fake_run_agent_factory([]))

    service.handle_message(user.pk, "nightly summary", "schedule", trigger_type=AgentRun.TriggerType.SCHEDULE)

    run = AgentRun.objects.get(user=user)
    assert run.trigger_type == AgentRun.TriggerType.SCHEDULE
    assert run.input_tokens == 123
    assert run.output_tokens == 45


@pytest.mark.django_db
def test_handle_message_persists_user_before_assistant(user, monkeypatch):
    from apps.agent import service

    actions = [
        AgentAction(
            index=0,
            type="tool_call",
            tool_call=ToolCallResult(
                tool_name="create_task",
                tool_input={"description": "Buy milk"},
                tool_output={"ok": True, "data": {"id": 1, "description": "Buy milk"}},
                summary="created task 1",
            ),
        ),
        AgentAction(index=1, type="user_message", user_message="Added Buy milk."),
    ]
    monkeypatch.setattr(service, "run_agent", _fake_run_agent_factory(actions))

    result = service.handle_message(user.pk, "add buy milk", "telegram:1")

    messages = list(ChatMessage.objects.filter(user=user).order_by("created_at", "id"))
    assert [(message.role, message.content) for message in messages] == [
        ("user", "add buy milk"),
        ("assistant", "Added Buy milk."),
    ]
    assert ToolCall.objects.filter(user=user, tool_name="create_task").count() == 1
    assert result == ["Added Buy milk."]


@pytest.mark.django_db
def test_profile_api_key_overrides_global_setting(user, monkeypatch, settings):
    from apps.agent import service

    UserProfile.objects.filter(user=user).update(
        preferences={"anthropic_api_key": "user-key"},
    )
    settings.ANTHROPIC_API_KEY = "global-key"
    captured = {}

    def fake_run_agent(request, tools, llm_client=None):
        captured["api_key"] = request.api_key
        return AgentResponse(actions=[], stopped_reason="completed")

    monkeypatch.setattr(service, "run_agent", fake_run_agent)

    service.handle_message(user.pk, "hello", "telegram:1")

    assert captured["api_key"] == "user-key"


@pytest.mark.django_db
def test_estimate_message_tokens_uses_built_request_context(user, monkeypatch):
    from apps.agent import service
    from apps.tasks.models import Task

    Task.objects.create(user=user, description="Buy milk")
    ChatMessage.objects.create(user=user, role="user", content="Earlier", channel="telegram:1")
    captured = {}

    def fake_estimate(request, tools, llm_client=None):
        captured["message"] = request.message
        captured["history_len"] = len(request.conversation_history)
        captured["open_tasks_len"] = len(request.open_tasks)
        return "estimate"

    monkeypatch.setattr(service, "estimate_initial_tokens", fake_estimate)

    result = service.estimate_message_tokens(user.pk, "Add oat milk", "telegram:1")

    assert result == "estimate"
    assert captured == {
        "message": "Add oat milk",
        "history_len": 1,
        "open_tasks_len": 1,
    }
