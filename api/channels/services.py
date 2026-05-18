from __future__ import annotations

import logging
from uuid import UUID

from django.utils import timezone

from channels.models import Channel, ChannelType, Conversation
from channels.runtime import (
    BaseConversation,
    DummyConversation,
    TelegramConversation,
    WebConversation,
)

logger = logging.getLogger(__name__)


def get_conversation(channel_id: UUID, conversation_id: UUID | None = None) -> BaseConversation:
    channel = Channel.objects.get(pk=channel_id)

    if conversation_id is not None:
        conversation = Conversation.objects.get(pk=conversation_id, channel_id=channel_id)
    else:
        conversation = (
            Conversation.objects.filter(channel_id=channel_id)
            .order_by("-updated_at", "-created_at")
            .first()
        )
        if conversation is None:
            conversation = Conversation.objects.create(channel=channel)
            logger.info(
                "[channels] created conversation channel_id=%s conversation_id=%s channel_type=%s",
                channel.pk,
                conversation.pk,
                channel.type,
            )

    match channel.type:
        case ChannelType.TELEGRAM:
            return TelegramConversation(channel, conversation)
        case ChannelType.WEB:
            return WebConversation(channel, conversation)
        case ChannelType.DUMMY:
            return DummyConversation(channel, conversation)
        case _:
            raise ValueError(f"Unknown channel type: {channel.type!r}")


def touch_conversation(conversation_id: UUID) -> None:
    Conversation.objects.filter(pk=conversation_id).update(updated_at=timezone.now())
