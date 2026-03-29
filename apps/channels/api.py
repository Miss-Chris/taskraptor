import re
import json
from datetime import datetime

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from ninja import Router, Schema
from ninja.security import django_auth

from .models import Channel, ChannelRequest, ChannelRequestStatus, ChannelType
from .telegram import TelegramApiError, send_telegram_message

router = Router(tags=["channels"])

JOIN_PATTERN = re.compile(r"^\s*JOIN\s+([A-Za-z0-9_\-]+)\s*$", re.IGNORECASE)


class ChannelRequestCreateIn(Schema):
    regenerate: bool = False


class PendingChannelRequestOut(Schema):
    join_code: str
    status: str
    created_at: datetime


class ChannelStatusOut(Schema):
    channel_type: str
    is_connected: bool
    connected_at: datetime | None = None
    telegram_chat_id: int | None = None
    telegram_username: str | None = None
    pending_request: PendingChannelRequestOut | None = None


def _get_pending_request(user) -> ChannelRequest | None:
    return (
        ChannelRequest.objects.filter(
            user=user,
            channel_type=ChannelType.TELEGRAM,
            status=ChannelRequestStatus.PENDING,
        )
        .order_by("-created_at")
        .first()
    )


def _serialize_channel_status(user) -> ChannelStatusOut:
    channel = (
        Channel.objects.filter(user=user, channel_type=ChannelType.TELEGRAM)
        .order_by("-created_at")
        .first()
    )
    pending_request = _get_pending_request(user)
    return ChannelStatusOut(
        channel_type=ChannelType.TELEGRAM,
        is_connected=channel is not None,
        connected_at=channel.connected_at if channel else None,
        telegram_chat_id=channel.telegram_chat_id if channel else None,
        telegram_username=channel.telegram_username if channel else None,
        pending_request=pending_request,
    )


@router.get("/", auth=django_auth, response=ChannelStatusOut)
def get_channels(request: HttpRequest):
    return _serialize_channel_status(request.user)


@router.delete("/telegram", auth=django_auth, response=ChannelStatusOut)
def unlink_telegram(request: HttpRequest):
    Channel.objects.filter(user=request.user, channel_type=ChannelType.TELEGRAM).delete()
    return _serialize_channel_status(request.user)


@router.post("/requests/telegram", auth=django_auth, response=ChannelStatusOut)
def create_telegram_request(request: HttpRequest, data: ChannelRequestCreateIn):
    pending_request = _get_pending_request(request.user)

    if pending_request and not data.regenerate:
        return _serialize_channel_status(request.user)

    if pending_request and data.regenerate:
        pending_request.status = ChannelRequestStatus.EXPIRED
        pending_request.save(update_fields=["status"])

    ChannelRequest.objects.create(
        user=request.user,
        channel_type=ChannelType.TELEGRAM,
    )
    return _serialize_channel_status(request.user)


def _send_message_safe(chat_id: int, text: str) -> None:
    try:
        send_telegram_message(chat_id, text)
    except TelegramApiError:
        return


def _handle_telegram_webhook_payload(payload: dict) -> dict:
    message = payload.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    username = (message.get("from") or {}).get("username")

    if not chat_id:
        return {"ok": True}

    match = JOIN_PATTERN.match(text)
    if not match:
        _send_message_safe(chat_id, "Send JOIN <code> to connect your TaskRaptor account.")
        return {"ok": True}

    join_code = match.group(1)

    with transaction.atomic():
        channel_for_chat = (
            Channel.objects.select_for_update()
            .filter(channel_type=ChannelType.TELEGRAM, telegram_chat_id=chat_id)
            .first()
        )
        request_match = (
            ChannelRequest.objects.select_for_update()
            .select_related("user")
            .filter(
                channel_type=ChannelType.TELEGRAM,
                join_code=join_code,
                status=ChannelRequestStatus.PENDING,
            )
            .first()
        )

        if not request_match:
            _send_message_safe(chat_id, "That code is invalid or already used. Create a new code in TaskRaptor and try again.")
            return {"ok": True}

        if channel_for_chat and channel_for_chat.user_id != request_match.user_id:
            _send_message_safe(chat_id, "This Telegram chat is already linked to another TaskRaptor account.")
            return {"ok": True}

        Channel.objects.update_or_create(
            user=request_match.user,
            channel_type=ChannelType.TELEGRAM,
            defaults={
                "telegram_chat_id": chat_id,
                "telegram_username": username,
                "connected_at": timezone.now(),
            },
        )

        request_match.status = ChannelRequestStatus.FULFILLED
        request_match.fulfilled_at = timezone.now()
        request_match.save(update_fields=["status", "fulfilled_at"])

    _send_message_safe(chat_id, "Telegram connected to your TaskRaptor account.")
    return {"ok": True}


@csrf_exempt
def telegram_webhook_view(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        payload = {}

    return JsonResponse(_handle_telegram_webhook_payload(payload))
