from __future__ import annotations

from celery import shared_task

from apps.channels.models import Channel, ChannelType
from apps.channels.telegram import TelegramApiError, send_telegram_message

from .models import AgentRun
from .service import handle_message


@shared_task
def run_agent2_for_telegram_message(chat_id: int, text: str) -> list[str]:
    channel = (
        Channel.objects.filter(channel_type=ChannelType.TELEGRAM, telegram_chat_id=chat_id)
        .select_related("user")
        .first()
    )
    if channel is None:
        return []

    user_messages = handle_message(
        user_id=channel.user_id,
        text=text,
        channel=f"telegram:{chat_id}",
    )
    _send_telegram_messages(chat_id, user_messages)
    return user_messages


@shared_task
def run_agent2_scheduled_prompt(user_id: int, text: str) -> list[str]:
    user_messages = handle_message(
        user_id=user_id,
        text=text,
        channel="schedule",
        trigger_type=AgentRun.TriggerType.SCHEDULE,
    )
    channel = (
        Channel.objects.filter(user_id=user_id, channel_type=ChannelType.TELEGRAM)
        .order_by("-created_at")
        .first()
    )
    if channel and channel.telegram_chat_id:
        _send_telegram_messages(channel.telegram_chat_id, user_messages)
    return user_messages


def _send_telegram_messages(chat_id: int, messages: list[str]) -> None:
    for message in messages:
        try:
            send_telegram_message(chat_id, message)
        except TelegramApiError:
            break
