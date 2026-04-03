import pytest
from django.utils import timezone

from apps.channels.api import _handle_telegram_webhook_payload
from apps.channels.models import Channel, ChannelType


@pytest.mark.django_db
def test_linked_chat_enqueues_agent_task(user, monkeypatch):
    from apps.agent.tasks import run_agent_for_telegram_message

    Channel.objects.create(
        user=user,
        channel_type=ChannelType.TELEGRAM,
        telegram_chat_id=456,
        connected_at=timezone.now(),
    )
    captured = {}

    monkeypatch.setattr(
        run_agent_for_telegram_message,
        "delay",
        lambda chat_id, text: captured.update({"chat_id": chat_id, "text": text}),
    )

    response = _handle_telegram_webhook_payload(
        {
            "message": {
                "chat": {"id": 456},
                "from": {"username": "alice"},
                "text": "Add buy milk",
            }
        }
    )

    assert response == {"ok": True}
    assert captured == {"chat_id": 456, "text": "Add buy milk"}
