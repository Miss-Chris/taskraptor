from datetime import datetime
from uuid import UUID

from ninja import Schema


class TelegramStatusOut(Schema):
    connected: bool
    bot_name: str


class JoinCodeOut(Schema):
    code: str
    expires_at: datetime
    bot_name: str


class ChatConversationCreateIn(Schema):
    title: str = ""


class ChatConversationStartIn(Schema):
    content: str


class ChatConversationUpdateIn(Schema):
    title: str


class ChatMessageCreateIn(Schema):
    content: str


class ChatMessageOut(Schema):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    agent_run_id: UUID | None
    created_at: datetime


class ChatRunOut(Schema):
    id: UUID
    conversation_id: UUID
    status: str
    error: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ChatConversationOut(Schema):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    latest_message: ChatMessageOut | None
    latest_run: ChatRunOut | None


class ChatConversationListOut(Schema):
    conversations: list[ChatConversationOut]
    count: int


class ChatConversationDetailOut(Schema):
    conversation: ChatConversationOut
    messages: list[ChatMessageOut]
    runs: list[ChatRunOut]


class ChatMessagesOut(Schema):
    messages: list[ChatMessageOut]
    count: int


class ChatSendMessageOut(Schema):
    message: ChatMessageOut
    run: ChatRunOut


class ChatStartConversationOut(Schema):
    conversation: ChatConversationOut
    message: ChatMessageOut
    run: ChatRunOut
