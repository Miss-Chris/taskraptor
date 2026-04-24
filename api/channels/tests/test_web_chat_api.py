from __future__ import annotations

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from agent.models import AgentRun, AgentRunStatus
from agent.schemas import AgentResult, NewMessage
from channels.models import Channel, ChannelType, Conversation, WebChatMessage, WebChatRole
from channels.web import get_or_create_default_web_channel, process_next_pending_web_message

REGISTER_URL = "/api/auth/register"
CONVERSATIONS_URL = "/api/chat/conversations"


@pytest.fixture
def client():
    return Client()


def _register_and_token(client: Client, email: str) -> str:
    response = client.post(
        REGISTER_URL,
        data={"email": email, "password": "secret123"},
        content_type="application/json",
    )
    assert response.status_code == 201
    return response.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.mark.django_db
def test_chat_conversations_require_authentication(client):
    response = client.get(CONVERSATIONS_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_conversation_create_list_detail_are_scoped_to_user(client):
    token = _register_and_token(client, "chat-scope@example.com")
    other_token = _register_and_token(client, "chat-other@example.com")

    create_response = client.post(
        CONVERSATIONS_URL,
        data={"title": "Planning"},
        content_type="application/json",
        **_auth(token),
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    list_response = client.get(CONVERSATIONS_URL, **_auth(token))
    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.json()["conversations"]] == [conversation_id]

    detail_response = client.get(
        f"{CONVERSATIONS_URL}/{conversation_id}",
        **_auth(token),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["conversation"]["title"] == "Planning"

    other_detail = client.get(
        f"{CONVERSATIONS_URL}/{conversation_id}",
        **_auth(other_token),
    )
    assert other_detail.status_code == 404


@pytest.mark.django_db
def test_update_conversation_title(client):
    token = _register_and_token(client, "chat-rename@example.com")
    create_response = client.post(
        CONVERSATIONS_URL,
        data={"title": "Old"},
        content_type="application/json",
        **_auth(token),
    )
    conversation_id = create_response.json()["id"]

    response = client.patch(
        f"{CONVERSATIONS_URL}/{conversation_id}",
        data={"title": "New title"},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "New title"


@pytest.mark.django_db
def test_send_message_returns_accepted_and_enqueues_pending_run(client, monkeypatch):
    token = _register_and_token(client, "chat-send@example.com")
    create_response = client.post(
        CONVERSATIONS_URL,
        data={"title": "Send"},
        content_type="application/json",
        **_auth(token),
    )
    conversation_id = create_response.json()["id"]
    delay_calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        "channels.web_api.process_web_message.delay",
        lambda conversation_id, message_id, agent_run_id: delay_calls.append(
            (conversation_id, message_id, agent_run_id)
        ),
    )

    response = client.post(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages",
        data={"content": "  Add a task  "},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["message"]["content"] == "Add a task"
    assert data["message"]["role"] == WebChatRole.USER
    assert data["run"]["status"] == AgentRunStatus.PENDING
    assert data["message"]["agent_run_id"] == data["run"]["id"]
    assert delay_calls == [(conversation_id, data["message"]["id"], data["run"]["id"])]

    run = AgentRun.objects.get(pk=data["run"]["id"])
    assert run.status == AgentRunStatus.PENDING
    assert WebChatMessage.objects.get(pk=data["message"]["id"]).agent_run_id == run.pk


@pytest.mark.django_db
def test_send_message_rejects_blank_content(client):
    token = _register_and_token(client, "chat-blank@example.com")
    create_response = client.post(
        CONVERSATIONS_URL,
        data={},
        content_type="application/json",
        **_auth(token),
    )
    conversation_id = create_response.json()["id"]

    response = client.post(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages",
        data={"content": "   "},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_other_user_cannot_send_to_conversation(client):
    token = _register_and_token(client, "chat-owner@example.com")
    other_token = _register_and_token(client, "chat-intruder@example.com")
    create_response = client.post(
        CONVERSATIONS_URL,
        data={},
        content_type="application/json",
        **_auth(token),
    )
    conversation_id = create_response.json()["id"]

    response = client.post(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages",
        data={"content": "hello"},
        content_type="application/json",
        **_auth(other_token),
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_message_polling_supports_before_and_after(client):
    token = _register_and_token(client, "chat-poll@example.com")
    create_response = client.post(
        CONVERSATIONS_URL,
        data={},
        content_type="application/json",
        **_auth(token),
    )
    conversation_id = create_response.json()["id"]
    conversation = Conversation.objects.get(pk=conversation_id)
    messages = [
        WebChatMessage.objects.create(
            conversation=conversation,
            role=WebChatRole.USER if i % 2 == 0 else WebChatRole.ASSISTANT,
            content=f"m{i}",
        )
        for i in range(5)
    ]

    tail = client.get(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages?limit=3",
        **_auth(token),
    )
    assert tail.status_code == 200
    assert [m["content"] for m in tail.json()["messages"]] == ["m2", "m3", "m4"]

    before = client.get(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages?limit=2&before_id={messages[2].pk}",
        **_auth(token),
    )
    assert before.status_code == 200
    assert [m["content"] for m in before.json()["messages"]] == ["m0", "m1"]

    after = client.get(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages?after_id={messages[2].pk}",
        **_auth(token),
    )
    assert after.status_code == 200
    assert [m["content"] for m in after.json()["messages"]] == ["m3", "m4"]


@pytest.mark.django_db
def test_run_polling_scopes_and_reports_status(client):
    token = _register_and_token(client, "chat-run@example.com")
    other_token = _register_and_token(client, "chat-run-other@example.com")
    create_response = client.post(
        CONVERSATIONS_URL,
        data={},
        content_type="application/json",
        **_auth(token),
    )
    conversation = Conversation.objects.get(pk=create_response.json()["id"])
    run = AgentRun.objects.create(
        channel=conversation.channel,
        conversation=conversation,
        user=conversation.channel.user,
        llm_model=conversation.channel.user.llm_models.first(),
        status=AgentRunStatus.RUNNING,
        started_at=timezone.now(),
    )

    response = client.get(f"/api/chat/runs/{run.pk}", **_auth(token))
    assert response.status_code == 200
    assert response.json()["status"] == AgentRunStatus.RUNNING

    AgentRun.objects.filter(pk=run.pk).update(
        status=AgentRunStatus.FAILED,
        error="boom",
        completed_at=timezone.now(),
    )
    failed_response = client.get(f"/api/chat/runs/{run.pk}", **_auth(token))
    assert failed_response.status_code == 200
    assert failed_response.json()["status"] == AgentRunStatus.FAILED
    assert failed_response.json()["error"] == "boom"

    other_response = client.get(f"/api/chat/runs/{run.pk}", **_auth(other_token))
    assert other_response.status_code == 404


@pytest.mark.django_db
def test_pending_web_messages_are_processed_as_separate_turns_in_order(client, monkeypatch):
    token = _register_and_token(client, "chat-order@example.com")
    create_response = client.post(
        CONVERSATIONS_URL,
        data={},
        content_type="application/json",
        **_auth(token),
    )
    conversation_id = create_response.json()["id"]
    monkeypatch.setattr(
        "channels.web_api.process_web_message.delay",
        lambda *_args: None,
    )

    client.post(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages",
        data={"content": "first"},
        content_type="application/json",
        **_auth(token),
    )
    client.post(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages",
        data={"content": "second"},
        content_type="application/json",
        **_auth(token),
    )
    seen_messages: list[str] = []

    def fake_run_agent(**kwargs):
        message = kwargs["new_message"]
        seen_messages.append(message)
        return AgentResult(
            response_text=f"reply {message}",
            new_messages=[
                NewMessage(actor="user", content=message),
                NewMessage(actor="assistant", content=f"reply {message}"),
            ],
        )

    monkeypatch.setattr("channels.workflow.run_agent", fake_run_agent)

    process_next_pending_web_message(conversation_id)
    process_next_pending_web_message(conversation_id)

    assert seen_messages == ["first", "second"]
    assert list(
        AgentRun.objects.filter(conversation_id=conversation_id)
        .order_by("created_at")
        .values_list("status", flat=True)
    ) == [AgentRunStatus.COMPLETED, AgentRunStatus.COMPLETED]
    assert list(
        WebChatMessage.objects.filter(conversation_id=conversation_id)
        .order_by("created_at")
        .values_list("content", flat=True)
    ) == ["first", "second", "reply first", "reply second"]


@pytest.mark.django_db
def test_failed_web_processing_does_not_create_visible_error_bubble(client, monkeypatch):
    token = _register_and_token(client, "chat-failure@example.com")
    assert token
    user = User.objects.get(email="chat-failure@example.com")
    channel = get_or_create_default_web_channel(user)
    conversation = Conversation.objects.create(channel=channel)
    run = AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=channel.user,
        llm_model=channel.user.llm_models.first(),
        status=AgentRunStatus.PENDING,
    )
    WebChatMessage.objects.create(
        conversation=conversation,
        role=WebChatRole.USER,
        content="fail",
        agent_run=run,
    )

    def fake_run_agent(**kwargs):
        return AgentResult(
            response_text="Something went wrong. Please try again.",
            new_messages=[
                NewMessage(actor="user", content=kwargs["new_message"]),
                NewMessage(actor="assistant", content="Something went wrong. Please try again."),
            ],
            error="model failed",
        )

    monkeypatch.setattr("channels.workflow.run_agent", fake_run_agent)

    process_next_pending_web_message(conversation.pk)
    run.refresh_from_db()

    assert run.status == AgentRunStatus.FAILED
    assert run.error == "model failed"
    assert list(
        WebChatMessage.objects.filter(conversation=conversation).values_list("content", flat=True)
    ) == ["fail"]
