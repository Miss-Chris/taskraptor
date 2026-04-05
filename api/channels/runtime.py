from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import Any

from channels.models import Channel, ChannelType, Conversation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversationMetadata:
    user_id: int
    channel_id: int
    conversation_id: int
    channel_type: str
    channel_external_id: str
    conversation_external_id: str
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, channel: Channel, conversation: Conversation) -> ConversationMetadata:
        return cls(
            user_id=channel.user_id,
            channel_id=channel.pk,
            conversation_id=conversation.pk,
            channel_type=channel.type,
            channel_external_id=channel.external_id or "",
            conversation_external_id=conversation.external_id or "",
        )


class BaseConversation(ABC):
    def __init__(
        self,
        channel: Channel,
        conversation: Conversation,
        metadata: ConversationMetadata | None = None,
    ) -> None:
        self.channel = channel
        self.conversation = conversation
        self.metadata = metadata or ConversationMetadata.from_rows(channel, conversation)

    def send_message(self, text: str, **kwargs: Any) -> None:
        logger.info(
            "[channels] send_message type=%s channel_id=%s conversation_id=%s text=%r",
            self.channel.type,
            self.channel.pk,
            self.conversation.pk,
            text,
        )


class TelegramConversation(BaseConversation):
    def send_message(self, text: str, **kwargs: Any) -> None:
        logger.info(
            "[channels][telegram] channel_id=%s conversation_id=%s text=%r",
            self.channel.pk,
            self.conversation.pk,
            text,
        )


class WebConversation(BaseConversation):
    def send_message(self, text: str, **kwargs: Any) -> None:
        logger.info(
            "[channels][web] channel_id=%s conversation_id=%s text=%r",
            self.channel.pk,
            self.conversation.pk,
            text,
        )


class DummyConversation(BaseConversation):
    _sent: dict[int, list[str]] = {}

    def send_message(self, text: str, **kwargs: Any) -> None:
        cid = self.conversation.pk
        bucket = self._sent.setdefault(cid, [])
        bucket.append(text)
        logger.info(
            "[channels][dummy] channel_id=%s conversation_id=%s text=%r (in_memory_count=%s)",
            self.channel.pk,
            cid,
            text,
            len(bucket),
        )
