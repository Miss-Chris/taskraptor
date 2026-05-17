from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.models import LlmModel
from channels.telegram_media import (
    NoImageCapableModelError,
    UnsupportedTelegramAttachmentError,
    build_attachment_user_message,
)


@pytest.mark.django_db
def test_build_attachment_user_message_for_text_document(test_user, monkeypatch):
    monkeypatch.setattr(
        "channels.telegram_media.download_telegram_file",
        lambda file_id: b"buy milk\ncall mom",
    )

    message = build_attachment_user_message(
        test_user,
        attachment_kind="document",
        file_id="doc-1",
        caption="today",
        file_name="notes.txt",
        mime_type="text/plain",
    )

    assert message == (
        "[Telegram text attachment: notes.txt]\n\n"
        "Caption: today\n\n"
        "Contents:\n"
        "buy milk\n"
        "call mom"
    )


@pytest.mark.django_db
def test_build_attachment_user_message_rejects_binary_document(test_user, monkeypatch):
    monkeypatch.setattr(
        "channels.telegram_media.download_telegram_file",
        lambda file_id: b"\x00\x01",
    )

    with pytest.raises(UnsupportedTelegramAttachmentError):
        build_attachment_user_message(
            test_user,
            attachment_kind="document",
            file_id="doc-1",
            file_name="archive.bin",
            mime_type="application/octet-stream",
        )


@pytest.mark.django_db
def test_build_attachment_user_message_for_photo_uses_image_capable_model(
    test_user,
    monkeypatch,
):
    deepseek = LlmModel.objects.create(
        user=test_user,
        model_key="deepseek/deepseek-chat",
        api_key="deepseek-key",
        is_active=True,
    )
    openai = LlmModel.objects.create(
        user=test_user,
        model_key="openai/gpt-4o-mini",
        api_key="openai-key",
        is_active=False,
    )
    monkeypatch.setattr(
        "channels.telegram_media.download_telegram_file",
        lambda file_id: b"fake-image",
    )
    calls = []

    def fake_llm(llm_model, messages, **kwargs):
        calls.append((llm_model, messages, kwargs))
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="A receipt for milk."))]
        )

    message = build_attachment_user_message(
        test_user,
        attachment_kind="photo",
        file_id="photo-1",
        caption="expense",
        mime_type="image/jpeg",
        llm_callable=fake_llm,
    )

    assert deepseek.supports_image_input is False
    assert openai.supports_image_input is True
    assert calls[0][0] == openai
    assert calls[0][1][1]["content"][1]["type"] == "image_url"
    assert message == (
        "[Telegram image attachment]\n\n"
        "Caption: expense\n\n"
        "Converted image content:\n"
        "A receipt for milk."
    )


@pytest.mark.django_db
def test_build_attachment_user_message_for_photo_requires_image_capable_model(
    test_user,
    monkeypatch,
):
    LlmModel.objects.create(
        user=test_user,
        model_key="deepseek/deepseek-chat",
        api_key="deepseek-key",
    )
    monkeypatch.setattr(
        "channels.telegram_media.download_telegram_file",
        lambda file_id: b"fake-image",
    )

    with pytest.raises(NoImageCapableModelError):
        build_attachment_user_message(
            test_user,
            attachment_kind="photo",
            file_id="photo-1",
            mime_type="image/jpeg",
        )
