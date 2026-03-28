"""
E2E: full task lifecycle through the HTTP API.

Requires a real Postgres database — no mocks. pytest-django creates and tears
down the test database automatically. Set DJANGO_SETTINGS_MODULE in pytest.ini
(already done) so it picks up the local settings with the DB config.
"""

import json

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.channels.models import Channel, ChannelRequest, ChannelRequestStatus, ChannelType
from apps.channels.telegram import get_telegram_webhook_url
from apps.tasks.models import Task


@pytest.mark.django_db
def test_full_task_lifecycle(anon_client: Client) -> None:
    # ------------------------------------------------------------------
    # 1. Create a user directly in the DB (simulates registration).
    # ------------------------------------------------------------------
    user = User.objects.create_user(email="raptor@example.com", password="hunter2!")
    assert user.pk is not None

    # ------------------------------------------------------------------
    # 2. Login via the API.
    # ------------------------------------------------------------------
    resp = anon_client.post(
        "/api/auth/login",
        data=json.dumps({"email": "raptor@example.com", "password": "hunter2!"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["email"] == "raptor@example.com"
    assert body["id"] == user.pk

    # ------------------------------------------------------------------
    # 3. Confirm /me returns the logged-in user.
    # ------------------------------------------------------------------
    resp = anon_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "raptor@example.com"

    # ------------------------------------------------------------------
    # 4. Create a task.
    # ------------------------------------------------------------------
    resp = anon_client.post(
        "/api/tasks/",
        data=json.dumps({"description": "Buy oat milk"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    task_data = resp.json()
    task_id: int = task_data["id"]
    assert task_data["description"] == "Buy oat milk"
    assert task_data["status"] == "pending"
    assert task_data["due_at"] is None

    # ------------------------------------------------------------------
    # 5. List tasks — should contain our new task.
    # ------------------------------------------------------------------
    resp = anon_client.get("/api/tasks/")
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert task_id in ids

    # ------------------------------------------------------------------
    # 6. Mark the task done.
    # ------------------------------------------------------------------
    resp = anon_client.patch(
        f"/api/tasks/{task_id}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "done"

    # ------------------------------------------------------------------
    # 7. Assert DB state — the source of truth.
    # ------------------------------------------------------------------
    task = Task.objects.get(pk=task_id)
    assert task.status == Task.Status.DONE
    assert task.user_id == user.pk
    assert task.description == "Buy oat milk"

    # ------------------------------------------------------------------
    # 8. Delete the task.
    # ------------------------------------------------------------------
    resp = anon_client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert not Task.objects.filter(pk=task_id).exists()

    # ------------------------------------------------------------------
    # 9. Logout.
    # ------------------------------------------------------------------
    resp = anon_client.post("/api/auth/logout")
    assert resp.status_code == 200

    # After logout, /me should return 401.
    resp = anon_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_healthcheck_reports_database_access(client: Client) -> None:
    User.objects.create_user(email="health@example.com", password="hunter2!")

    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["database"] == "reachable"
    assert resp.json()["user_count"] == 1


@pytest.mark.django_db
@override_settings(
    NINJA_CSRF=True,
    MIDDLEWARE=[
        "django.middleware.security.SecurityMiddleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ],
)
def test_task_create_with_enforced_csrf_bootstrap() -> None:
    client = Client(enforce_csrf_checks=True)
    user = User.objects.create_user(email="csrf@example.com", password="hunter2!")

    csrf_resp = client.get("/api/auth/csrf")
    assert csrf_resp.status_code == 200
    csrftoken = csrf_resp.cookies["csrftoken"].value

    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({"email": "csrf@example.com", "password": "hunter2!"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrftoken,
    )
    assert login_resp.status_code == 200, login_resp.content
    assert login_resp.json()["id"] == user.pk
    csrftoken = client.cookies["csrftoken"].value

    create_resp = client.post(
        "/api/tasks/",
        data=json.dumps({"description": "CSRF-safe task"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrftoken,
    )
    assert create_resp.status_code == 200, create_resp.content
    assert create_resp.json()["description"] == "CSRF-safe task"


@pytest.mark.django_db
def test_create_telegram_channel_request_is_idempotent(anon_client: Client) -> None:
    user = User.objects.create_user(email="telegram@example.com", password="hunter2!")
    login_resp = anon_client.post(
        "/api/auth/login",
        data=json.dumps({"email": "telegram@example.com", "password": "hunter2!"}),
        content_type="application/json",
    )
    assert login_resp.status_code == 200, login_resp.content

    first = anon_client.post(
        "/api/channels/requests/telegram",
        data=json.dumps({"regenerate": False}),
        content_type="application/json",
    )
    assert first.status_code == 200, first.content
    first_code = first.json()["pending_request"]["join_code"]

    second = anon_client.post(
        "/api/channels/requests/telegram",
        data=json.dumps({"regenerate": False}),
        content_type="application/json",
    )
    assert second.status_code == 200, second.content
    assert second.json()["pending_request"]["join_code"] == first_code

    regenerate = anon_client.post(
        "/api/channels/requests/telegram",
        data=json.dumps({"regenerate": True}),
        content_type="application/json",
    )
    assert regenerate.status_code == 200, regenerate.content
    next_code = regenerate.json()["pending_request"]["join_code"]
    assert next_code != first_code

    assert ChannelRequest.objects.filter(user=user, status=ChannelRequestStatus.PENDING).count() == 1
    assert ChannelRequest.objects.filter(user=user, status=ChannelRequestStatus.EXPIRED).count() == 1


@pytest.mark.django_db
def test_telegram_webhook_links_account_and_replaces_existing_chat(monkeypatch) -> None:
    sent_messages: list[tuple[int, str]] = []

    def fake_send_telegram_message(chat_id: int, text: str) -> dict:
        sent_messages.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr("apps.channels.api.send_telegram_message", fake_send_telegram_message)

    client = Client()
    user = User.objects.create_user(email="join@example.com", password="hunter2!")
    request_record = ChannelRequest.objects.create(user=user, channel_type=ChannelType.TELEGRAM)

    first_resp = client.post(
        "/api/channels/telegram/webhook",
        data=json.dumps(
            {
                "update_id": 1,
                "message": {
                    "text": f"JOIN {request_record.join_code}",
                    "chat": {"id": 101},
                    "from": {"username": "raptor"},
                },
            }
        ),
        content_type="application/json",
    )
    assert first_resp.status_code == 200, first_resp.content

    channel = Channel.objects.get(user=user, channel_type=ChannelType.TELEGRAM)
    assert channel.telegram_chat_id == 101
    assert channel.telegram_username == "raptor"
    request_record.refresh_from_db()
    assert request_record.status == ChannelRequestStatus.FULFILLED

    second_request = ChannelRequest.objects.create(user=user, channel_type=ChannelType.TELEGRAM)
    second_resp = client.post(
        "/api/channels/telegram/webhook",
        data=json.dumps(
            {
                "update_id": 2,
                "message": {
                    "text": f"JOIN {second_request.join_code}",
                    "chat": {"id": 202},
                    "from": {"username": "raptor_new"},
                },
            }
        ),
        content_type="application/json",
    )
    assert second_resp.status_code == 200, second_resp.content

    channel.refresh_from_db()
    assert channel.telegram_chat_id == 202
    assert channel.telegram_username == "raptor_new"
    assert sent_messages[-1] == (202, "Telegram connected to your TaskRaptor account.")


@pytest.mark.django_db
def test_telegram_webhook_rejects_invalid_code(monkeypatch) -> None:
    sent_messages: list[tuple[int, str]] = []

    def fake_send_telegram_message(chat_id: int, text: str) -> dict:
        sent_messages.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr("apps.channels.api.send_telegram_message", fake_send_telegram_message)

    client = Client()
    resp = client.post(
        "/api/channels/telegram/webhook",
        data=json.dumps(
            {
                "update_id": 3,
                "message": {
                    "text": "JOIN not-a-real-code",
                    "chat": {"id": 404},
                },
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert not Channel.objects.exists()
    assert sent_messages[-1] == (
        404,
        "That code is invalid or already used. Create a new code in TaskRaptor and try again.",
    )


@pytest.mark.django_db
def test_telegram_webhook_rejects_chat_already_linked_to_another_user(monkeypatch) -> None:
    sent_messages: list[tuple[int, str]] = []

    def fake_send_telegram_message(chat_id: int, text: str) -> dict:
        sent_messages.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr("apps.channels.api.send_telegram_message", fake_send_telegram_message)

    client = Client()
    first_user = User.objects.create_user(email="one@example.com", password="hunter2!")
    second_user = User.objects.create_user(email="two@example.com", password="hunter2!")
    Channel.objects.create(
        user=first_user,
        channel_type=ChannelType.TELEGRAM,
        telegram_chat_id=777,
        connected_at=timezone.now(),
    )
    request_record = ChannelRequest.objects.create(user=second_user, channel_type=ChannelType.TELEGRAM)

    resp = client.post(
        "/api/channels/telegram/webhook",
        data=json.dumps(
            {
                "update_id": 4,
                "message": {
                    "text": f"JOIN {request_record.join_code}",
                    "chat": {"id": 777},
                },
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    request_record.refresh_from_db()
    assert request_record.status == ChannelRequestStatus.PENDING
    assert sent_messages[-1] == (
        777,
        "This Telegram chat is already linked to another TaskRaptor account.",
    )


@override_settings(
    TELEGRAM_BOT_TOKEN="bot-token",
    TELEGRAM_WEBHOOK_BASE_URL="https://example.ngrok.app",
)
def test_set_telegram_webhook_command(monkeypatch, capsys) -> None:
    called: list[bool] = []

    def fake_set_telegram_webhook() -> dict:
        called.append(True)
        return {"ok": True, "result": True}

    monkeypatch.setattr(
        "apps.channels.management.commands.set_telegram_webhook.set_telegram_webhook",
        fake_set_telegram_webhook,
    )

    call_command("set_telegram_webhook")
    out = capsys.readouterr().out

    assert called == [True]
    assert get_telegram_webhook_url() in out
    assert '"ok": true' in out


@override_settings(
    TELEGRAM_BOT_TOKEN="",
    TELEGRAM_WEBHOOK_BASE_URL="",
)
def test_set_telegram_webhook_command_requires_configuration() -> None:
    with pytest.raises(Exception) as exc_info:
        call_command("set_telegram_webhook")

    assert "TELEGRAM_WEBHOOK_BASE_URL is not configured" in str(exc_info.value)
