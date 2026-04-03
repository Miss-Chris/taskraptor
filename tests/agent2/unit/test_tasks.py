import pytest
from django.utils import timezone

from apps.channels.models import Channel, ChannelType


@pytest.mark.django_db
def test_run_agent2_for_telegram_message_sends_responses(user, monkeypatch):
    from apps.agent2.tasks import run_agent2_for_telegram_message

    Channel.objects.create(
        user=user,
        channel_type=ChannelType.TELEGRAM,
        telegram_chat_id=123,
        connected_at=timezone.now(),
    )
    sent_messages = []

    monkeypatch.setattr(
        "apps.agent2.tasks.handle_message",
        lambda **kwargs: ["First reply", "Second reply"],
    )
    monkeypatch.setattr(
        "apps.agent2.tasks.send_telegram_message",
        lambda chat_id, text: sent_messages.append((chat_id, text)),
    )

    result = run_agent2_for_telegram_message(123, "What do I have?")

    assert result == ["First reply", "Second reply"]
    assert sent_messages == [
        (123, "First reply"),
        (123, "Second reply"),
    ]


@pytest.mark.django_db
def test_run_agent2_scheduled_prompt_uses_schedule_trigger_and_sends_to_latest_channel(user, monkeypatch):
    from apps.agent2.tasks import run_agent2_scheduled_prompt

    Channel.objects.create(
        user=user,
        channel_type=ChannelType.TELEGRAM,
        telegram_chat_id=789,
        connected_at=timezone.now(),
    )
    sent_messages = []
    captured = {}

    def fake_handle_message(**kwargs):
        captured.update(kwargs)
        return ["Scheduled reply"]

    monkeypatch.setattr("apps.agent2.tasks.handle_message", fake_handle_message)
    monkeypatch.setattr(
        "apps.agent2.tasks.send_telegram_message",
        lambda chat_id, text: sent_messages.append((chat_id, text)),
    )

    result = run_agent2_scheduled_prompt(user.pk, "Send me a digest")

    assert result == ["Scheduled reply"]
    assert captured["trigger_type"] == "schedule"
    assert sent_messages == [(789, "Scheduled reply")]
