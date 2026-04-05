from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from django.db.models import QuerySet

from agent.schemas import AgentResult
from channels.models import Channel, ChannelType, Conversation, WebChatMessage, WebChatRole

if TYPE_CHECKING:
    from agent.models import AgentRun

DEFAULT_WEB_CHANNEL_NAME = "Web"


def get_or_create_default_web_channel(user) -> Channel:
    """Return the user's web channel, creating it if needed."""
    channel, _created = Channel.objects.get_or_create(
        user=user,
        type=ChannelType.WEB,
        defaults={"name": DEFAULT_WEB_CHANNEL_NAME},
    )
    return channel


def create_web_conversation(channel: Channel, title: str = "") -> Conversation:
    """Create a new conversation on a web channel (e.g. \"New chat\")."""
    return Conversation.objects.create(channel=channel, title=title)


def record_user_message(conversation: Conversation, text: str) -> WebChatMessage:
    """Persist an incoming user-visible message."""
    from channels.services import touch_conversation

    message = WebChatMessage.objects.create(
        conversation=conversation,
        role=WebChatRole.USER,
        content=text,
    )
    touch_conversation(conversation.pk)
    return message


def record_assistant_message(
    conversation: Conversation,
    text: str,
    agent_run: AgentRun | None = None,
) -> WebChatMessage:
    """Persist an assistant reply shown in the web UI."""
    from channels.services import touch_conversation

    message = WebChatMessage.objects.create(
        conversation=conversation,
        role=WebChatRole.ASSISTANT,
        content=text,
        agent_run=agent_run,
    )
    touch_conversation(conversation.pk)
    return message


def get_chat_history(
    conversation_id: int,
    *,
    limit: int = 50,
    before_id: int | None = None,
) -> QuerySet[WebChatMessage]:
    """
    Return up to ``limit`` web chat messages in chronological order (oldest first).

    Without ``before_id``, returns the most recent ``limit`` messages (the
    current \"tail\" of the thread). With ``before_id``, returns the ``limit``
    messages strictly older than that row (for loading earlier history).
    """
    qs = WebChatMessage.objects.filter(conversation_id=conversation_id)
    if before_id is not None:
        qs = qs.filter(pk__lt=before_id)
    pks = list(qs.order_by("-created_at", "-pk").values_list("pk", flat=True)[:limit])
    pks.reverse()
    return WebChatMessage.objects.filter(pk__in=pks).order_by("created_at", "pk")


def handle_web_user_message(
    conversation: Conversation,
    message: str,
    llm_callable: Callable | None = None,
) -> AgentResult:
    """
    Record the user message, run the agent workflow, return the result.

    Assistant replies are persisted via ``WebConversation.send_message`` during
    ``handle_user_incoming`` (one ``WebChatMessage`` per ``respond_to_user``).
    """
    from channels.workflow import handle_user_incoming

    record_user_message(conversation, message)
    return handle_user_incoming(conversation, message, llm_callable=llm_callable)
