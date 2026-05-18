from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.test import Client
from django.test import override_settings

from channels.telegram import (
    download_telegram_file,
    get_telegram_file,
    send_telegram_message,
    set_telegram_webhook,
)
from channels.telegram_format import markdown_to_telegram_html
from channels.tasks import (
    process_telegram_attachment,
    process_telegram_join,
    process_telegram_text,
)
from channels.telegram_handlers import (
    JOIN_FAILURE_MESSAGE,
    JOIN_SUCCESS_MESSAGE,
    NO_IMAGE_MODEL_MESSAGE,
    NO_ACTIVE_MODEL_MESSAGE,
    UNSUPPORTED_ATTACHMENT_MESSAGE,
    UNLINKED_CHAT_MESSAGE,
    WORKFLOW_FAILURE_MESSAGE,
    handle_telegram_attachment,
    handle_telegram_join,
    handle_telegram_text,
    safe_send_telegram_message,
)
from channels.telegram_media import (
    NoImageCapableModelError,
    UnsupportedTelegramAttachmentError,
)
from channels.telegram_webhook import (
    IGNORE_EVENT,
    TelegramWebhookEvent,
    parse_telegram_webhook_body,
)
from channels.workflow import NoActiveLlmModel

WEBHOOK_URL = "/api/telegram/webhook"


@pytest.fixture
def client() -> Client:
    return Client()


def test_markdown_to_telegram_html_converts_common_assistant_formatting():
    text = "Done! **||Buy oranges||**\n\nUse `milk <2%>` and _soon_."

    assert markdown_to_telegram_html(text) == (
        "Done! <b><tg-spoiler>Buy oranges</tg-spoiler></b>\n\n"
        "Use <code>milk &lt;2%&gt;</code> and <i>soon</i>."
    )


@override_settings(TELEGRAM_BOT_TOKEN="test-token")
def test_send_telegram_message_uses_html_parse_mode(monkeypatch):
    requests = []

    class FakeResponse:
        text = '{"ok": true, "result": {"message_id": 1}}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "result": {"message_id": 1}}

    def fake_post(url, *, json, timeout):
        requests.append((url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr("channels.telegram.httpx.post", fake_post)

    result = send_telegram_message("123", "Done! **Buy oranges**")

    assert result["ok"] is True
    assert len(requests) == 1
    url, payload, timeout = requests[0]
    assert timeout == 30
    assert url.endswith("/sendMessage")
    assert payload == {
        "chat_id": "123",
        "text": "Done! <b>Buy oranges</b>",
        "parse_mode": "HTML",
    }


@override_settings(
    TELEGRAM_BOT_TOKEN="test-token",
    TELEGRAM_WEBHOOK_BASE_URL="https://taskraptor.example.com",
    TELEGRAM_WEBHOOK_SECRET="webhook-secret",
)
def test_set_telegram_webhook_sends_secret_token(monkeypatch):
    requests = []

    class FakeResponse:
        text = '{"ok": true, "result": true}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "result": True}

    def fake_post(url, *, json, timeout):
        requests.append((url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr("channels.telegram.httpx.post", fake_post)

    result = set_telegram_webhook()

    assert result["ok"] is True
    url, payload, timeout = requests[0]
    assert timeout == 30
    assert url.endswith("/setWebhook")
    assert payload == {
        "url": "https://taskraptor.example.com/api/telegram/webhook",
        "secret_token": "webhook-secret",
    }


def test_parse_telegram_webhook_body_invalid_json_returns_ignore():
    assert parse_telegram_webhook_body("{") == IGNORE_EVENT


def test_parse_telegram_webhook_body_non_dict_returns_ignore():
    assert parse_telegram_webhook_body("[]") == IGNORE_EVENT


def test_parse_telegram_webhook_body_caption_only_returns_ignore():
    payload = (
        '{"message": {"chat": {"id": 123}, "caption": "photo caption"}}'
    )

    assert parse_telegram_webhook_body(payload) == IGNORE_EVENT


def test_parse_telegram_webhook_body_photo_uses_largest_size():
    payload = json.dumps(
        {
            "message": {
                "chat": {"id": 123},
                "caption": "receipt",
                "photo": [
                    {"file_id": "small", "file_size": 10, "width": 10, "height": 10},
                    {"file_id": "large", "file_size": 20, "width": 20, "height": 20},
                ],
            }
        }
    )

    assert parse_telegram_webhook_body(payload) == TelegramWebhookEvent(
        action="attachment",
        chat_id="123",
        attachment_kind="photo",
        file_id="large",
        mime_type="image/jpeg",
        caption="receipt",
    )


def test_parse_telegram_webhook_body_document_routes_as_attachment():
    payload = json.dumps(
        {
            "message": {
                "chat": {"id": 123},
                "caption": "notes",
                "document": {
                    "file_id": "doc-1",
                    "file_name": "notes.txt",
                    "mime_type": "text/plain",
                },
            }
        }
    )

    assert parse_telegram_webhook_body(payload) == TelegramWebhookEvent(
        action="attachment",
        chat_id="123",
        attachment_kind="document",
        file_id="doc-1",
        file_name="notes.txt",
        mime_type="text/plain",
        caption="notes",
    )


def test_parse_telegram_webhook_body_join_command_is_normalized():
    payload = (
        '{"message": {"chat": {"id": 123}, "text": "  join abc123  "}}'
    )

    assert parse_telegram_webhook_body(payload) == TelegramWebhookEvent(
        action="join",
        chat_id="123",
        text="join abc123",
        join_code="ABC123",
    )


def test_parse_telegram_webhook_body_edited_message_routes_as_text():
    payload = (
        '{"edited_message": {"chat": {"id": 123}, "text": "  hello there  "}}'
    )

    assert parse_telegram_webhook_body(payload) == TelegramWebhookEvent(
        action="text",
        chat_id="123",
        text="hello there",
    )


def test_telegram_webhook_invalid_json_returns_ok_and_enqueues_nothing(client, monkeypatch):
    join_calls: list[tuple[str, str]] = []
    text_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_join.delay",
        lambda chat_id, join_code: join_calls.append((chat_id, join_code)),
    )
    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda chat_id, text: text_calls.append((chat_id, text)),
    )

    response = client.post(WEBHOOK_URL, data="{", content_type="application/json")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert join_calls == []
    assert text_calls == []


def test_telegram_webhook_unsupported_update_returns_ok_and_enqueues_nothing(
    client,
    monkeypatch,
):
    join_calls: list[tuple[str, str]] = []
    text_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_join.delay",
        lambda chat_id, join_code: join_calls.append((chat_id, join_code)),
    )
    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda chat_id, text: text_calls.append((chat_id, text)),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"message": {"chat": {"id": 123}, "caption": "photo caption"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert join_calls == []
    assert text_calls == []


def test_telegram_webhook_blank_text_returns_ok_and_enqueues_nothing(client, monkeypatch):
    join_calls: list[tuple[str, str]] = []
    text_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_join.delay",
        lambda chat_id, join_code: join_calls.append((chat_id, join_code)),
    )
    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda chat_id, text: text_calls.append((chat_id, text)),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"message": {"chat": {"id": 123}, "text": "   "}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert join_calls == []
    assert text_calls == []


@override_settings(TELEGRAM_WEBHOOK_SECRET="webhook-secret")
def test_telegram_webhook_rejects_invalid_secret_token(client, monkeypatch):
    text_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda chat_id, text: text_calls.append((chat_id, text)),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"message": {"chat": {"id": 123}, "text": "hello"}},
        content_type="application/json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong",
    )

    assert response.status_code == 403
    assert response.json() == {"ok": False}
    assert text_calls == []


@override_settings(TELEGRAM_BOT_TOKEN="test-token")
def test_get_and_download_telegram_file(monkeypatch):
    post_requests = []
    get_requests = []

    class FakeJsonResponse:
        text = '{"ok": true, "result": {"file_path": "docs/note.txt"}}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "result": {"file_path": "docs/note.txt"}}

    class FakeFileResponse:
        text = "hello"
        content = b"hello"

        def raise_for_status(self):
            return None

    def fake_post(url, *, json, timeout):
        post_requests.append((url, json, timeout))
        return FakeJsonResponse()

    def fake_get(url, *, timeout):
        get_requests.append((url, timeout))
        return FakeFileResponse()

    monkeypatch.setattr("channels.telegram.httpx.post", fake_post)
    monkeypatch.setattr("channels.telegram.httpx.get", fake_get)

    assert get_telegram_file("file-1") == {"file_path": "docs/note.txt"}
    assert download_telegram_file("file-1") == b"hello"
    assert post_requests == [
        (
            "https://api.telegram.org/bottest-token/getFile",
            {"file_id": "file-1"},
            30,
        ),
        (
            "https://api.telegram.org/bottest-token/getFile",
            {"file_id": "file-1"},
            30,
        ),
    ]
    assert get_requests == [
        ("https://api.telegram.org/file/bottest-token/docs/note.txt", 30)
    ]


@override_settings(TELEGRAM_WEBHOOK_SECRET="webhook-secret")
def test_telegram_webhook_accepts_valid_secret_token(client, monkeypatch):
    text_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda chat_id, text: text_calls.append((chat_id, text)),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"message": {"chat": {"id": 123}, "text": "hello"}},
        content_type="application/json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="webhook-secret",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert text_calls == [("123", "hello")]


def test_telegram_webhook_join_command_enqueues_join_task(client, monkeypatch):
    join_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_join.delay",
        lambda chat_id, join_code: join_calls.append((chat_id, join_code)),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"message": {"chat": {"id": 123}, "text": "JOIN abc123"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert join_calls == [("123", "ABC123")]


def test_telegram_webhook_text_enqueues_text_task(client, monkeypatch):
    text_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda chat_id, text: text_calls.append((chat_id, text)),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"message": {"chat": {"id": 123}, "text": "  hello there  "}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert text_calls == [("123", "hello there")]


def test_telegram_webhook_text_enqueue_failure_notifies_user(client, monkeypatch):
    send_calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("broker down")),
    )
    monkeypatch.setattr(
        "channels.api.safe_send_telegram_message",
        lambda chat_id, text, *, log_context: send_calls.append(
            (chat_id, text, log_context)
        ),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"message": {"chat": {"id": 123}, "text": "ping"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert send_calls == [("123", WORKFLOW_FAILURE_MESSAGE, "text enqueue error")]


def test_telegram_webhook_attachment_enqueues_attachment_task(client, monkeypatch):
    attachment_calls: list[tuple[str, str, str, str, str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_attachment.delay",
        lambda *args: attachment_calls.append(args),
    )

    response = client.post(
        WEBHOOK_URL,
        data={
            "message": {
                "chat": {"id": 123},
                "caption": "notes",
                "document": {
                    "file_id": "doc-1",
                    "file_name": "notes.txt",
                    "mime_type": "text/plain",
                },
            }
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert attachment_calls == [
        ("123", "document", "doc-1", "notes", "notes.txt", "text/plain")
    ]


def test_telegram_webhook_edited_message_enqueues_text_task(client, monkeypatch):
    text_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda chat_id, text: text_calls.append((chat_id, text)),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"edited_message": {"chat": {"id": 456}, "text": "edited"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert text_calls == [("456", "edited")]


def test_telegram_webhook_dispatches_without_inline_execution(client, monkeypatch):
    text_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.api.handle_user_incoming",
        lambda *args, **kwargs: pytest.fail("webhook should not run workflow inline"),
        raising=False,
    )
    monkeypatch.setattr(
        "channels.api.redeem_join_code",
        lambda *args, **kwargs: pytest.fail("webhook should not redeem join codes inline"),
        raising=False,
    )
    monkeypatch.setattr(
        "channels.api.send_telegram_message",
        lambda *args, **kwargs: pytest.fail("webhook should not send replies inline"),
        raising=False,
    )
    monkeypatch.setattr(
        "channels.api.process_telegram_text.delay",
        lambda chat_id, text: text_calls.append((chat_id, text)),
    )

    response = client.post(
        WEBHOOK_URL,
        data={"message": {"chat": {"id": 999}, "text": "ping"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert text_calls == [("999", "ping")]


def test_handle_telegram_join_success_sends_confirmation(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.redeem_join_code",
        lambda join_code, chat_id: calls.append(("redeem", join_code, chat_id)),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: calls.append(("send", chat_id, text)),
    )

    handle_telegram_join("123", "ABC123")

    assert calls == [
        ("redeem", "ABC123", "123"),
        ("send", "123", JOIN_SUCCESS_MESSAGE),
    ]


def test_handle_telegram_join_invalid_code_sends_validation_message(monkeypatch):
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.redeem_join_code",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Invalid join code.")),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_join("123", "ABC123")

    assert send_calls == [("123", "Invalid join code.")]


def test_handle_telegram_join_unexpected_error_sends_generic_message(monkeypatch):
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.redeem_join_code",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_join("123", "ABC123")

    assert send_calls == [("123", JOIN_FAILURE_MESSAGE)]


def test_handle_telegram_text_unlinked_chat_sends_join_hint(monkeypatch):
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: None,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_text("123", "hello")

    assert send_calls == [("123", UNLINKED_CHAT_MESSAGE)]


def test_handle_telegram_attachment_unlinked_chat_sends_join_hint(monkeypatch):
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: None,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_attachment("123", "photo", "photo-1")

    assert send_calls == [("123", UNLINKED_CHAT_MESSAGE)]


def test_handle_telegram_attachment_unsupported_sends_notice(monkeypatch):
    send_calls: list[tuple[str, str]] = []
    channel = SimpleNamespace(pk=7, user=object())

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: channel,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.build_attachment_user_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(UnsupportedTelegramAttachmentError()),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_attachment("123", "document", "doc-1")

    assert send_calls == [("123", UNSUPPORTED_ATTACHMENT_MESSAGE)]


def test_handle_telegram_attachment_without_image_model_sends_notice(monkeypatch):
    send_calls: list[tuple[str, str]] = []
    channel = SimpleNamespace(pk=7, user=object())

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: channel,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.build_attachment_user_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(NoImageCapableModelError()),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_attachment("123", "photo", "photo-1")

    assert send_calls == [("123", NO_IMAGE_MODEL_MESSAGE)]


def test_handle_telegram_text_linked_chat_runs_workflow(monkeypatch):
    channel = SimpleNamespace(pk=7)
    conversation = object()
    workflow_calls: list[tuple[object, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: channel,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.get_conversation",
        lambda channel_id: SimpleNamespace(conversation=conversation),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.handle_user_incoming",
        lambda convo, text: workflow_calls.append((convo, text)),
    )

    handle_telegram_text("123", "  hello  ")

    assert workflow_calls == [(conversation, "hello")]


def test_handle_telegram_text_no_active_model_sends_notice(monkeypatch):
    channel = SimpleNamespace(pk=7)
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: channel,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.get_conversation",
        lambda channel_id: SimpleNamespace(conversation=object()),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.handle_user_incoming",
        lambda *args, **kwargs: (_ for _ in ()).throw(NoActiveLlmModel("missing model")),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_text("123", "hello")

    assert send_calls == [("123", NO_ACTIVE_MODEL_MESSAGE)]


def test_handle_telegram_text_unexpected_error_sends_generic_message(monkeypatch):
    channel = SimpleNamespace(pk=7)
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: channel,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.get_conversation",
        lambda channel_id: SimpleNamespace(conversation=object()),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.handle_user_incoming",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_text("123", "hello")

    assert send_calls == [("123", WORKFLOW_FAILURE_MESSAGE)]


def test_handle_telegram_text_conversation_lookup_error_sends_generic_message(monkeypatch):
    channel = SimpleNamespace(pk=7)
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: channel,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.get_conversation",
        lambda channel_id: (_ for _ in ()).throw(RuntimeError("db unavailable")),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_text("123", "hello")

    assert send_calls == [("123", WORKFLOW_FAILURE_MESSAGE)]


def test_handle_telegram_text_channel_lookup_error_sends_generic_message(monkeypatch):
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: (_ for _ in ()).throw(RuntimeError("db unavailable")),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_text("123", "hello")

    assert send_calls == [("123", WORKFLOW_FAILURE_MESSAGE)]


def test_handle_telegram_attachment_conversation_lookup_error_sends_generic_message(monkeypatch):
    channel = SimpleNamespace(pk=7, user=object())
    send_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.telegram_handlers.find_channel_by_telegram_chat_id",
        lambda chat_id: channel,
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.build_attachment_user_message",
        lambda *args, **kwargs: "attachment text",
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.get_conversation",
        lambda channel_id: (_ for _ in ()).throw(RuntimeError("db unavailable")),
    )
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda chat_id, text: send_calls.append((chat_id, text)),
    )

    handle_telegram_attachment("123", "photo", "photo-1")

    assert send_calls == [("123", WORKFLOW_FAILURE_MESSAGE)]


def test_safe_send_telegram_message_logs_and_suppresses_send_failures(monkeypatch, caplog):
    monkeypatch.setattr(
        "channels.telegram_handlers.send_telegram_message",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    with caplog.at_level("ERROR"):
        result = safe_send_telegram_message(
            "123",
            "hello",
            log_context="test send failure",
        )

    assert result is False
    assert "failed to send test send failure chat_id=123" in caplog.text


def test_process_telegram_join_task_delegates_to_handler(monkeypatch):
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.tasks.handle_telegram_join",
        lambda chat_id, join_code: calls.append((chat_id, join_code)),
    )

    process_telegram_join("123", "ABC123")

    assert calls == [("123", "ABC123")]


def test_process_telegram_text_task_delegates_to_handler(monkeypatch):
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "channels.tasks.handle_telegram_text",
        lambda chat_id, text: calls.append((chat_id, text)),
    )

    process_telegram_text("123", "hello")

    assert calls == [("123", "hello")]


def test_process_telegram_attachment_task_delegates_to_handler(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "channels.tasks.handle_telegram_attachment",
        lambda chat_id, attachment_kind, file_id, **kwargs: calls.append(
            (chat_id, attachment_kind, file_id, kwargs)
        ),
    )

    process_telegram_attachment(
        123,
        "document",
        "doc-1",
        "notes",
        "notes.txt",
        "text/plain",
    )

    assert calls == [
        (
            "123",
            "document",
            "doc-1",
            {
                "caption": "notes",
                "file_name": "notes.txt",
                "mime_type": "text/plain",
            },
        )
    ]
