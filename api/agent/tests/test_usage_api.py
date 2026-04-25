from __future__ import annotations

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from agent.models import (
    AgentRun,
    AgentRunStatus,
    LlmModel,
    MessageActor,
    MessageLog,
    SYSTEM_FREE_MODEL_KEY,
)
from channels.models import Conversation
from channels.web import get_or_create_default_web_channel

REGISTER_URL = "/api/auth/register"
USAGE_SUMMARY_URL = "/api/usage/summary"
USAGE_MODELS_URL = "/api/usage/models"


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


def _user(email: str) -> User:
    return User.objects.get(email=email)


@pytest.mark.django_db
def test_usage_summary_redacts_models_and_reports_request_quota_and_byo_token_totals(client):
    token = _register_and_token(client, "usage-summary@example.com")
    user = _user("usage-summary@example.com")
    system_model = LlmModel.objects.get(user=user, model_key=SYSTEM_FREE_MODEL_KEY)
    system_model.quota = 100
    system_model.quota_used = 35
    system_model.quota_expires_at = timezone.now() + timezone.timedelta(days=1)
    system_model.save(update_fields=["quota", "quota_used", "quota_expires_at", "updated_at"])
    byo_model = LlmModel.objects.create(
        user=user,
        model_key="deepseek/deepseek-chat",
        api_key="secret-key",
        context_message_limit=12,
        is_active=False,
    )
    channel = get_or_create_default_web_channel(user)
    conversation = Conversation.objects.create(channel=channel, title="Usage")
    completed_run = AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=user,
        llm_model=system_model,
        status=AgentRunStatus.COMPLETED,
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    old_system_run = AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=user,
        llm_model=system_model,
        status=AgentRunStatus.COMPLETED,
        started_at=timezone.now() - timezone.timedelta(days=40),
        completed_at=timezone.now() - timezone.timedelta(days=40),
    )
    AgentRun.objects.filter(pk=old_system_run.pk).update(
        created_at=timezone.now() - timezone.timedelta(days=40),
    )
    AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=user,
        llm_model=system_model,
        status=AgentRunStatus.FAILED,
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=user,
        llm_model=system_model,
        status=AgentRunStatus.PENDING,
    )
    AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=user,
        llm_model=system_model,
        status=AgentRunStatus.CANCELLED,
    )
    byo_run = AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=user,
        llm_model=byo_model,
        status=AgentRunStatus.COMPLETED,
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    MessageLog.objects.create(
        agent_run=completed_run,
        conversation=conversation,
        channel=channel,
        actor=MessageActor.ASSISTANT,
        content="Done",
        input_tokens=11,
        output_tokens=7,
    )
    MessageLog.objects.create(
        agent_run=byo_run,
        conversation=conversation,
        channel=channel,
        actor=MessageActor.ASSISTANT,
        content="BYO done",
        input_tokens=13,
        output_tokens=5,
    )
    old_byo_run = AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=user,
        llm_model=byo_model,
        status=AgentRunStatus.COMPLETED,
    )
    AgentRun.objects.filter(pk=old_byo_run.pk).update(
        created_at=timezone.now() - timezone.timedelta(days=31),
    )
    MessageLog.objects.create(
        agent_run=old_byo_run,
        conversation=conversation,
        channel=channel,
        actor=MessageActor.ASSISTANT,
        content="Old BYO done",
        input_tokens=100,
        output_tokens=100,
    )

    response = client.get(USAGE_SUMMARY_URL, **_auth(token))

    assert response.status_code == 200
    data = response.json()
    assert data["system_model"]["quota"] == 100
    assert data["system_model"]["quota_used"] == 2
    assert data["system_model"]["quota_remaining"] == 98
    assert data["system_model"]["is_available"] is True
    assert data["totals"]["input_tokens"] == 13
    assert data["totals"]["output_tokens"] == 5
    assert data["totals"]["total_tokens"] == 18
    assert data["totals"]["recent_run_count"] == 5
    assert data["totals"]["failed_run_count"] == 1
    models = {row["model_key"]: row for row in data["models"]}
    assert models[SYSTEM_FREE_MODEL_KEY]["has_api_key"] is False
    assert models[SYSTEM_FREE_MODEL_KEY]["quota_used"] == 2
    assert models[SYSTEM_FREE_MODEL_KEY]["quota_remaining"] == 98
    assert models["deepseek/deepseek-chat"]["has_api_key"] is True
    assert "api_key" not in models["deepseek/deepseek-chat"]
    assert SYSTEM_FREE_MODEL_KEY not in [
        option["model_key"] for option in data["supported_models"]
    ]


@pytest.mark.django_db
def test_usage_summary_uses_settings_quota_when_system_model_quota_is_null(client, settings):
    settings.SYSTEM_FREE_MONTHLY_REQUEST_QUOTA = 50
    token = _register_and_token(client, "usage-settings-quota@example.com")
    user = _user("usage-settings-quota@example.com")
    system_model = LlmModel.objects.get(user=user, model_key=SYSTEM_FREE_MODEL_KEY)
    system_model.quota = None
    system_model.save(update_fields=["quota", "updated_at"])
    channel = get_or_create_default_web_channel(user)
    conversation = Conversation.objects.create(channel=channel, title="Settings quota")

    AgentRun.objects.create(
        channel=channel,
        conversation=conversation,
        user=user,
        llm_model=system_model,
        status=AgentRunStatus.COMPLETED,
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )

    response = client.get(USAGE_SUMMARY_URL, **_auth(token))

    assert response.status_code == 200
    data = response.json()
    assert data["system_model"]["quota"] == 50
    assert data["system_model"]["quota_used"] == 1
    assert data["system_model"]["quota_remaining"] == 49
    models = {row["model_key"]: row for row in data["models"]}
    assert models[SYSTEM_FREE_MODEL_KEY]["quota"] == 50
    assert models[SYSTEM_FREE_MODEL_KEY]["quota_remaining"] == 49


@pytest.mark.django_db
def test_create_usage_model_rejects_unsupported_model_and_blank_api_key(client):
    token = _register_and_token(client, "usage-create-invalid@example.com")

    unsupported = client.post(
        USAGE_MODELS_URL,
        data={"model_key": "openai/gpt-4.1", "api_key": "sk-test"},
        content_type="application/json",
        **_auth(token),
    )
    blank_key = client.post(
        USAGE_MODELS_URL,
        data={"model_key": "deepseek/deepseek-chat", "api_key": "   "},
        content_type="application/json",
        **_auth(token),
    )
    system_create = client.post(
        USAGE_MODELS_URL,
        data={"model_key": SYSTEM_FREE_MODEL_KEY, "api_key": ""},
        content_type="application/json",
        **_auth(token),
    )

    assert unsupported.status_code == 400
    assert blank_key.status_code == 400
    assert system_create.status_code == 400


@pytest.mark.django_db
def test_create_and_update_usage_model_manage_key_context_and_active_state(client):
    token = _register_and_token(client, "usage-update@example.com")
    user = _user("usage-update@example.com")
    system_model = LlmModel.objects.get(user=user, model_key=SYSTEM_FREE_MODEL_KEY)

    create_response = client.post(
        USAGE_MODELS_URL,
        data={
            "model_key": "deepseek/deepseek-chat",
            "api_key": "first-key",
            "context_message_limit": 50,
            "is_active": True,
        },
        content_type="application/json",
        **_auth(token),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["has_api_key"] is True
    assert created["is_active"] is True
    system_model.refresh_from_db()
    assert system_model.is_active is False

    update_response = client.patch(
        f"{USAGE_MODELS_URL}/{created['id']}",
        data={"api_key": "second-key", "context_message_limit": 8},
        content_type="application/json",
        **_auth(token),
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["context_message_limit"] == 8
    assert updated["is_active"] is True
    model = LlmModel.objects.get(pk=created["id"])
    assert model.api_key == "second-key"

    system_update = client.patch(
        f"{USAGE_MODELS_URL}/{system_model.pk}",
        data={"api_key": "not-allowed", "context_message_limit": 9, "is_active": False},
        content_type="application/json",
        **_auth(token),
    )
    invalid_context = client.patch(
        f"{USAGE_MODELS_URL}/{created['id']}",
        data={"context_message_limit": 0},
        content_type="application/json",
        **_auth(token),
    )

    assert system_update.status_code == 400
    assert invalid_context.status_code == 400


@pytest.mark.django_db
def test_activate_usage_model_makes_exactly_one_model_active(client):
    token = _register_and_token(client, "usage-activate@example.com")
    user = _user("usage-activate@example.com")
    first = LlmModel.objects.create(
        user=user,
        model_key="deepseek/deepseek-chat",
        api_key="first",
        is_active=False,
    )
    second = LlmModel.objects.create(
        user=user,
        model_key="anthropic/claude-sonnet-4-6",
        api_key="second",
        is_active=False,
    )

    response = client.post(f"{USAGE_MODELS_URL}/{second.pk}/activate", **_auth(token))

    assert response.status_code == 200
    active_models = list(
        LlmModel.objects.filter(user=user, is_active=True).values_list("pk", flat=True)
    )
    assert active_models == [second.pk]
    first.refresh_from_db()
    assert first.is_active is False


@pytest.mark.django_db
def test_delete_usage_model_rejects_system_active_and_cross_user_models(client):
    token = _register_and_token(client, "usage-delete@example.com")
    other_token = _register_and_token(client, "usage-delete-other@example.com")
    user = _user("usage-delete@example.com")
    system_model = LlmModel.objects.get(user=user, model_key=SYSTEM_FREE_MODEL_KEY)
    inactive_model = LlmModel.objects.create(
        user=user,
        model_key="deepseek/deepseek-chat",
        api_key="delete-me",
        is_active=False,
    )
    active_model = LlmModel.objects.create(
        user=user,
        model_key="anthropic/claude-sonnet-4-6",
        api_key="active",
        is_active=False,
    )
    client.post(f"{USAGE_MODELS_URL}/{active_model.pk}/activate", **_auth(token))

    system_delete = client.delete(f"{USAGE_MODELS_URL}/{system_model.pk}", **_auth(token))
    active_delete = client.delete(f"{USAGE_MODELS_URL}/{active_model.pk}", **_auth(token))
    cross_user_delete = client.delete(f"{USAGE_MODELS_URL}/{inactive_model.pk}", **_auth(other_token))
    inactive_delete = client.delete(f"{USAGE_MODELS_URL}/{inactive_model.pk}", **_auth(token))

    assert system_delete.status_code == 400
    assert active_delete.status_code == 400
    assert cross_user_delete.status_code == 404
    assert inactive_delete.status_code == 204
    assert LlmModel.objects.filter(pk=inactive_model.pk).exists() is False
