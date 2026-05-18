from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from agent.models import AgentRun, AgentRunStatus, LlmModel, get_or_create_system_model
from agent.schemas import AgentResult
from channels.models import Channel, ChannelType, Conversation, WebChatMessage, WebChatRole

if TYPE_CHECKING:
    from accounts.models import User

DEFAULT_WEB_CHANNEL_NAME = "Web"
logger = logging.getLogger(__name__)


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
    conversation = Conversation.objects.create(channel=channel, title=title)
    logger.info(
        "[web] created conversation channel_id=%s conversation_id=%s",
        channel.pk,
        conversation.pk,
    )
    return conversation


def _active_llm_model_for_user(user: User) -> LlmModel:
    llm_model = (
        LlmModel.objects.filter(user=user, is_active=True)
        .order_by("model_key", "-created_at")
        .first()
    )
    if llm_model is None:
        llm_model = get_or_create_system_model(user)
    return llm_model


def record_user_message(
    conversation: Conversation,
    text: str,
    agent_run: AgentRun | None = None,
) -> WebChatMessage:
    """Persist an incoming user-visible message."""
    from channels.services import touch_conversation

    message = WebChatMessage.objects.create(
        conversation=conversation,
        role=WebChatRole.USER,
        content=text,
        agent_run=agent_run,
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
    conversation_id: UUID,
    *,
    limit: int = 50,
    before_id: UUID | None = None,
) -> QuerySet[WebChatMessage]:
    """
    Return up to ``limit`` web chat messages in chronological order (oldest first).

    Without ``before_id``, returns the most recent ``limit`` messages (the
    current \"tail\" of the thread). With ``before_id``, returns the ``limit``
    messages strictly older than that row (for loading earlier history).
    """
    qs = WebChatMessage.objects.filter(conversation_id=conversation_id)
    if before_id is not None:
        try:
            before = WebChatMessage.objects.only("created_at").get(
                pk=before_id,
                conversation_id=conversation_id,
            )
        except ObjectDoesNotExist:
            return WebChatMessage.objects.none()
        qs = qs.filter(created_at__lt=before.created_at)
    pks = list(qs.order_by("-created_at").values_list("pk", flat=True)[:limit])
    pks.reverse()
    return WebChatMessage.objects.filter(pk__in=pks).order_by("created_at")


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


def queue_web_user_message(conversation: Conversation, message: str) -> tuple[WebChatMessage, AgentRun]:
    """Persist a user bubble and pending run for asynchronous web processing."""
    llm_model = _active_llm_model_for_user(conversation.channel.user)
    agent_run = AgentRun.objects.create(
        channel=conversation.channel,
        conversation=conversation,
        user=conversation.channel.user,
        llm_model=llm_model,
        status=AgentRunStatus.PENDING,
    )
    web_message = record_user_message(conversation, message, agent_run=agent_run)
    logger.info(
        "[web] queued message conversation_id=%s message_id=%s agent_run_id=%s",
        conversation.pk,
        web_message.pk,
        agent_run.pk,
    )
    return web_message, agent_run


def process_next_pending_web_message(
    conversation_id: UUID,
    *,
    llm_callable: Callable | None = None,
) -> AgentRun | None:
    """
    Process the oldest pending web user message for a conversation.

    The conversation row lock serializes agent runs per conversation. Each queued
    task handles one pending turn; if tasks execute out of order, the oldest
    pending run is still selected first.
    """
    from channels.workflow import handle_user_incoming

    with transaction.atomic():
        conversation = (
            Conversation.objects.select_for_update()
            .select_related("channel", "channel__user")
            .get(pk=conversation_id, channel__type=ChannelType.WEB)
        )
        pending_run = (
            AgentRun.objects.select_for_update()
            .filter(
                conversation=conversation,
                status=AgentRunStatus.PENDING,
                web_messages__role=WebChatRole.USER,
            )
            .order_by("created_at", "id")
            .first()
        )
        if pending_run is None:
            logger.warning(
                "[web] no pending run conversation_id=%s",
                conversation.pk,
            )
            return None

        web_message = (
            WebChatMessage.objects.filter(
                conversation=conversation,
                role=WebChatRole.USER,
                agent_run=pending_run,
            )
            .order_by("created_at", "id")
            .first()
        )
        if web_message is None:
            logger.error(
                "[web] missing queued message conversation_id=%s agent_run_id=%s",
                conversation.pk,
                pending_run.pk,
            )
            pending_run.status = AgentRunStatus.FAILED
            pending_run.error = "Missing queued web user message."
            pending_run.save(update_fields=["status", "error"])
            return pending_run

        logger.info(
            "[web] processing message conversation_id=%s message_id=%s agent_run_id=%s",
            conversation.pk,
            web_message.pk,
            pending_run.pk,
        )
        try:
            handle_user_incoming(
                conversation,
                web_message.content,
                llm_callable=llm_callable,
                agent_run=pending_run,
                deliver_on_error=False,
            )
        except Exception as exc:
            logger.exception(
                "[web] processing failed conversation_id=%s message_id=%s agent_run_id=%s",
                conversation.pk,
                web_message.pk,
                pending_run.pk,
            )
            pending_run.status = AgentRunStatus.FAILED
            pending_run.error = str(exc)
            pending_run.completed_at = timezone.now()
            pending_run.save(update_fields=["status", "error", "completed_at"])
        pending_run.refresh_from_db()
        logger.info(
            "[web] processed message conversation_id=%s message_id=%s agent_run_id=%s status=%s",
            conversation.pk,
            web_message.pk,
            pending_run.pk,
            pending_run.status,
        )
        return pending_run
