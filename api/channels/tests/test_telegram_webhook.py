from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.test import Client

from channels.tasks import process_telegram_join, process_telegram_text
from channels.telegram_handlers import (
    JOIN_FAILURE_MESSAGE,
    JOIN_SUCCESS_MESSAGE,
    NO_ACTIVE_MODEL_MESSAGE,
    UNLINKED_CHAT_MESSAGE,
    WORKFLOW_FAILURE_MESSAGE,
    handle_telegram_join,
    handle_telegram_text,
    safe_send_telegram_message,
)
from channels.telegram_webhook import IGNORE_EVENT, TelegramWebhookEvent, parse_telegram_webhook_body
from channels.workflow import NoActiveLlmModel

WEBHOOK_URL = "/api/telegram/webhook"


@pytest.fixture
def client() -> Client:
    return Client()


def test_parse_telegram_webhook_body_invalid_json_returns_ignore():
    assert parse_telegram_webhook_body("{") == IGNORE_EVENT


def test_parse_telegram_webhook_body_non_dict_returns_ignore():
    assert parse_telegram_webhook_body("[]") == IGNORE_EVENT


def test_parse_telegram_webhook_body_caption_only_returns_ignore():
    payload = (
        '{"message": {"chat": {"id": 123}, "caption": "photo caption"}}'
    )

    assert parse_telegram_webhook_body(payload) == IGNORE_EVENT


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
