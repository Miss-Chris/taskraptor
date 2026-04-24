from __future__ import annotations

import logging
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.http import AuthedHttpRequest
from accounts.schemas import ErrorOut
from agent.models import AgentRun, AgentRunStatus
from channels.models import ChannelType, Conversation, WebChatMessage
from channels.schemas import (
    ChatConversationCreateIn,
    ChatConversationDetailOut,
    ChatConversationListOut,
    ChatConversationOut,
    ChatConversationUpdateIn,
    ChatMessageCreateIn,
    ChatMessageOut,
    ChatMessagesOut,
    ChatRunOut,
    ChatSendMessageOut,
)
from channels.tasks import process_web_message
from channels.web import (
    create_web_conversation,
    get_chat_history,
    get_or_create_default_web_channel,
    queue_web_user_message,
)

logger = logging.getLogger(__name__)

router = Router(tags=["chat"], auth=AuthBearer())


def _safe_limit(value: int, *, default: int = 50, maximum: int = 200) -> int:
    if value is None:
        return default
    return max(1, min(value, maximum))


def _conversation_queryset(user) -> QuerySet[Conversation]:
    return Conversation.objects.filter(
        channel__user=user,
        channel__type=ChannelType.WEB,
    ).select_related("channel")


def _get_conversation(user, conversation_id: UUID) -> Conversation:
    return _conversation_queryset(user).get(pk=conversation_id)


def _to_message_out(message: WebChatMessage) -> ChatMessageOut:
    return ChatMessageOut(
        id=message.pk,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        agent_run_id=message.agent_run_id,
        created_at=message.created_at,
    )


def _to_run_out(run: AgentRun) -> ChatRunOut:
    return ChatRunOut(
        id=run.pk,
        conversation_id=run.conversation_id,
        status=run.status,
        error=run.error,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _latest_message(conversation: Conversation) -> WebChatMessage | None:
    return (
        WebChatMessage.objects.filter(conversation=conversation)
        .order_by("-created_at", "-id")
        .first()
    )


def _latest_run(conversation: Conversation) -> AgentRun | None:
    return (
        AgentRun.objects.filter(conversation=conversation)
        .order_by("-created_at", "-id")
        .first()
    )


def _to_conversation_out(conversation: Conversation) -> ChatConversationOut:
    latest_message = _latest_message(conversation)
    latest_run = _latest_run(conversation)
    return ChatConversationOut(
        id=conversation.pk,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        latest_message=_to_message_out(latest_message) if latest_message else None,
        latest_run=_to_run_out(latest_run) if latest_run else None,
    )


def _messages_after(conversation: Conversation, after_id: UUID, limit: int) -> QuerySet[WebChatMessage]:
    try:
        after = WebChatMessage.objects.only("created_at").get(
            pk=after_id,
            conversation=conversation,
        )
    except ObjectDoesNotExist:
        return WebChatMessage.objects.none()
    return (
        WebChatMessage.objects.filter(
            conversation=conversation,
            created_at__gt=after.created_at,
        )
        .order_by("created_at")[:limit]
    )


def _recent_runs(conversation: Conversation, limit: int = 20) -> list[ChatRunOut]:
    runs = (
        AgentRun.objects.filter(conversation=conversation)
        .order_by("-created_at", "-id")[:limit]
    )
    return [_to_run_out(run) for run in runs]


@router.get(
    "/conversations",
    response={200: ChatConversationListOut, 401: ErrorOut},
)
def list_chat_conversations(request: AuthedHttpRequest, limit: int = 50):
    get_or_create_default_web_channel(request.auth)
    conversations = list(
        _conversation_queryset(request.auth)
        .order_by("-updated_at", "-created_at")[: _safe_limit(limit)]
    )
    return Status(
        200,
        ChatConversationListOut(
            conversations=[_to_conversation_out(conversation) for conversation in conversations],
            count=len(conversations),
        ),
    )


@router.post(
    "/conversations",
    response={201: ChatConversationOut, 400: ErrorOut, 401: ErrorOut},
)
def create_chat_conversation(request: AuthedHttpRequest, payload: ChatConversationCreateIn):
    channel = get_or_create_default_web_channel(request.auth)
    title = payload.title.strip()
    if len(title) > 255:
        return Status(400, {"detail": "Title must be 255 characters or fewer."})
    conversation = create_web_conversation(channel, title=title)
    return Status(201, _to_conversation_out(conversation))


@router.get(
    "/conversations/{conversation_id}",
    response={200: ChatConversationDetailOut, 401: ErrorOut, 404: ErrorOut},
)
def get_chat_conversation(
    request: AuthedHttpRequest,
    conversation_id: UUID,
    message_limit: int = 50,
    run_limit: int = 20,
):
    try:
        conversation = _get_conversation(request.auth, conversation_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    messages = list(get_chat_history(conversation.pk, limit=_safe_limit(message_limit)))
    return Status(
        200,
        ChatConversationDetailOut(
            conversation=_to_conversation_out(conversation),
            messages=[_to_message_out(message) for message in messages],
            runs=_recent_runs(conversation, limit=_safe_limit(run_limit, default=20)),
        ),
    )


@router.patch(
    "/conversations/{conversation_id}",
    response={200: ChatConversationOut, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
)
def update_chat_conversation(
    request: AuthedHttpRequest,
    conversation_id: UUID,
    payload: ChatConversationUpdateIn,
):
    try:
        conversation = _get_conversation(request.auth, conversation_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    title = payload.title.strip()
    if len(title) > 255:
        return Status(400, {"detail": "Title must be 255 characters or fewer."})
    conversation.title = title
    conversation.save(update_fields=["title", "updated_at"])
    return Status(200, _to_conversation_out(conversation))


@router.get(
    "/conversations/{conversation_id}/messages",
    response={200: ChatMessagesOut, 401: ErrorOut, 404: ErrorOut},
)
def list_chat_messages(
    request: AuthedHttpRequest,
    conversation_id: UUID,
    limit: int = 50,
    before_id: UUID | None = None,
    after_id: UUID | None = None,
):
    try:
        conversation = _get_conversation(request.auth, conversation_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    safe_limit = _safe_limit(limit)
    if after_id is not None:
        messages = list(_messages_after(conversation, after_id, safe_limit))
    else:
        messages = list(
            get_chat_history(
                conversation.pk,
                limit=safe_limit,
                before_id=before_id,
            )
        )
    return Status(
        200,
        ChatMessagesOut(
            messages=[_to_message_out(message) for message in messages],
            count=len(messages),
        ),
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response={202: ChatSendMessageOut, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut, 500: ErrorOut},
)
def send_chat_message(
    request: AuthedHttpRequest,
    conversation_id: UUID,
    payload: ChatMessageCreateIn,
):
    try:
        conversation = _get_conversation(request.auth, conversation_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})

    content = payload.content.strip()
    if not content:
        return Status(400, {"detail": "Message content cannot be blank."})

    message, run = queue_web_user_message(conversation, content)
    try:
        process_web_message.delay(str(conversation.pk), str(message.pk), str(run.pk))
    except Exception as exc:
        logger.exception(
            "web chat: failed to enqueue message conversation_id=%s run_id=%s",
            conversation.pk,
            run.pk,
        )
        run.status = AgentRunStatus.FAILED
        run.error = f"Enqueue failed: {exc}"
        run.save(update_fields=["status", "error"])
        return Status(500, {"detail": "Failed to enqueue message."})

    run.refresh_from_db()
    message.refresh_from_db()
    return Status(
        202,
        ChatSendMessageOut(
            message=_to_message_out(message),
            run=_to_run_out(run),
        ),
    )


@router.get(
    "/runs/{run_id}",
    response={200: ChatRunOut, 401: ErrorOut, 404: ErrorOut},
)
def get_chat_run(request: AuthedHttpRequest, run_id: UUID):
    try:
        run = AgentRun.objects.get(
            pk=run_id,
            user=request.auth,
            channel__type=ChannelType.WEB,
        )
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Not found."})
    return Status(200, _to_run_out(run))
