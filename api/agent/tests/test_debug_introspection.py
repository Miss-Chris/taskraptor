from __future__ import annotations

import json
from datetime import time
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User, UserSession
from agent.models import LlmModel, MessageLog
from automations.models import Automation
from channels.models import Channel, ChannelType, Conversation, WebChatMessage
from channels.tests.scripted_llm import ScriptedLlm, tool_call_response
from channels.web import handle_web_user_message
from tasks.models import Task, TaskAuditLog


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def debug_user(db):
    return User.objects.create_user(
        email="debug@example.com",
        password="testpass123",
        prompt_instructions="Keep replies short.",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="other-debug@example.com", password="testpass123")


@pytest.fixture
def debug_token(debug_user):
    return str(UserSession.objects.create(user=debug_user).token)


@pytest.fixture
def debug_conversation(debug_user):
    model = LlmModel.objects.create(
        user=debug_user,
        model_key="deepseek/deepseek-chat",
        api_key="sk-debug-secret",
        quota=1000,
        quota_used=25,
        context_message_limit=7,
    )
    channel = Channel.objects.create(
        user=debug_user,
        name="Web",
        type=ChannelType.WEB,
    )
    conversation = Conversation.objects.create(channel=channel, title="Debug thread")
    task = Task.objects.create(user=debug_user, name="Original task")
    Automation.objects.create(
        user=debug_user,
        prompt="Summarize my day",
        schedule_time=time(9, 30),
    )
    scripted = ScriptedLlm(
        [
            tool_call_response("edit_task", {"task_id": str(task.pk), "name": "Updated task"}),
            tool_call_response("respond_to_user", {"message": "Updated it."}),
        ]
    )
    result = handle_web_user_message(
        conversation,
        "Rename the original task",
        llm_callable=scripted,
    )
    scripted.assert_exhausted()
    assert result.error is None
    assert model.api_key == "sk-debug-secret"
    return conversation


@pytest.mark.django_db
def test_debug_conversations_are_scoped_to_authenticated_user(
    client,
    debug_user,
    debug_token,
    debug_conversation,
    other_user,
):
    other_channel = Channel.objects.create(
        user=other_user,
        name="Other",
        type=ChannelType.WEB,
    )
    other_conversation = Conversation.objects.create(
        channel=other_channel,
        title="Other user's thread",
    )

    response = client.get(
        "/api/debug/conversations",
        HTTP_AUTHORIZATION=f"Bearer {debug_token}",
    )

    assert response.status_code == 200
    data = response.json()
    ids = {row["id"] for row in data["conversations"]}
    assert str(debug_conversation.pk) in ids
    assert str(other_conversation.pk) not in ids


@pytest.mark.django_db
def test_debug_conversation_rejects_other_users_conversation(
    client,
    debug_token,
    other_user,
):
    other_channel = Channel.objects.create(
        user=other_user,
        name="Other",
        type=ChannelType.WEB,
    )
    other_conversation = Conversation.objects.create(channel=other_channel)

    response = client.get(
        f"/api/debug/conversations/{other_conversation.pk}",
        HTTP_AUTHORIZATION=f"Bearer {debug_token}",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_debug_bundle_contains_agent_details_and_redacts_secrets(
    client,
    debug_token,
    debug_conversation,
):
    response = client.get(
        f"/api/debug/conversations/{debug_conversation.pk}",
        HTTP_AUTHORIZATION=f"Bearer {debug_token}",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "debug@example.com"
    assert data["user"]["prompt_instructions_present"] is True
    assert data["channel"]["type"] == "web"
    assert len(data["visible_messages"]) == 2
    assert data["visible_messages"][0]["content"] == "Rename the original task"
    assert data["agent_runs"][0]["status"] == "completed"
    assert data["agent_runs"][0]["input_tokens"] > 0
    assert any(log["actor"] == "tool_call" for log in data["message_logs"])
    assert any(log["tool_name"] == "edit_task" for log in data["message_logs"])
    assert data["related_tasks"][0]["name"] == "Updated task"
    assert data["task_audit_logs"][0]["action"] == "name_changed"
    assert data["automations"][0]["prompt"] == "Summarize my day"
    assert data["llm_models"][0]["api_key"] == "[redacted]"
    assert data["llm_models"][0]["has_api_key"] is True
    assert "sk-debug-secret" not in json.dumps(data)


@pytest.mark.django_db
def test_debug_summary_requires_authentication(client):
    response = client.get("/api/debug/summary")
    assert response.status_code == 401


@pytest.mark.django_db
def test_dump_agent_debug_outputs_markdown_and_redacts_secret(debug_conversation):
    out = StringIO()
    call_command(
        "dump_agent_debug",
        "--user-email",
        "debug@example.com",
        "--conversation-id",
        str(debug_conversation.pk),
        stdout=out,
    )

    text = out.getvalue()
    assert "# TaskRaptor Agent Debug Snapshot" in text
    assert "Rename the original task" in text
    assert "Updated task" in text
    assert "api_key=[redacted]" in text
    assert "sk-debug-secret" not in text


@pytest.mark.django_db
def test_dump_agent_debug_outputs_json_and_is_user_scoped(debug_conversation, other_user):
    out = StringIO()
    call_command(
        "dump_agent_debug",
        "--user-email",
        "debug@example.com",
        "--conversation-id",
        str(debug_conversation.pk),
        "--format",
        "json",
        stdout=out,
    )
    data = json.loads(out.getvalue())
    assert data["conversation"]["id"] == str(debug_conversation.pk)
    assert data["llm_models"][0]["api_key"] == "[redacted]"

    with pytest.raises(Exception) as exc:
        call_command(
            "dump_agent_debug",
            "--user-email",
            other_user.email,
            "--conversation-id",
            str(debug_conversation.pk),
            stdout=StringIO(),
        )
    assert "Conversation not found for user" in str(exc.value)


@pytest.mark.django_db
def test_debug_bundle_can_filter_to_one_run(client, debug_token, debug_conversation):
    run_id = WebChatMessage.objects.filter(
        conversation=debug_conversation,
        agent_run__isnull=False,
    ).values_list("agent_run_id", flat=True).get()
    response = client.get(
        f"/api/debug/conversations/{debug_conversation.pk}?run_id={run_id}",
        HTTP_AUTHORIZATION=f"Bearer {debug_token}",
    )

    assert response.status_code == 200
    data = response.json()
    assert [run["id"] for run in data["agent_runs"]] == [str(run_id)]
    assert {
        log["agent_run_id"] for log in data["message_logs"]
    } == {str(run_id)}
    assert MessageLog.objects.filter(agent_run_id=run_id).count() == len(data["message_logs"])
    assert TaskAuditLog.objects.filter(task__user__email="debug@example.com").exists()
