from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.schemas import ErrorOut
from channels.schemas import JoinCodeOut, TelegramStatusOut
from channels.tasks import process_telegram_join, process_telegram_text
from channels.telegram import create_join_code, get_active_telegram_channel, set_telegram_webhook
from channels.telegram_webhook import parse_telegram_webhook_body

logger = logging.getLogger(__name__)

router = Router(tags=["telegram"])


def _telegram_bot_name() -> str:
    return (getattr(settings, "TELEGRAM_BOT_NAME", "") or "").strip()

@router.post("/webhook")
def telegram_webhook(request: HttpRequest) -> JsonResponse:
    event = parse_telegram_webhook_body(request.body)

    if event.action == "join" and event.chat_id and event.join_code:
        try:
            process_telegram_join.delay(event.chat_id, event.join_code)
        except Exception:
            logger.exception(
                "telegram webhook: failed to enqueue join chat_id=%s",
                event.chat_id,
            )
    elif event.action == "text" and event.chat_id:
        try:
            process_telegram_text.delay(event.chat_id, event.text)
        except Exception:
            logger.exception(
                "telegram webhook: failed to enqueue text chat_id=%s",
                event.chat_id,
            )

    return JsonResponse({"ok": True})


@router.post("/reset-webhook")
def telegram_reset_webhook(request: HttpRequest) -> JsonResponse:
    """
    Calls Telegram ``setWebhook`` using configured base URL and bot token.
    Intended for operators after changing ``TELEGRAM_WEBHOOK_BASE_URL`` or tunnel URL.
    """
    try:
        result = set_telegram_webhook()
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
    return JsonResponse({"ok": True, "result": result})


@router.get(
    "/status",
    auth=AuthBearer(),
    response={200: TelegramStatusOut, 401: ErrorOut},
)
def telegram_status(request):
    user = request.auth
    connected = get_active_telegram_channel(user) is not None
    return Status(200, TelegramStatusOut(connected=connected, bot_name=_telegram_bot_name()))


@router.post(
    "/join-code",
    auth=AuthBearer(),
    response={200: JoinCodeOut, 401: ErrorOut},
)
def telegram_join_code(request):
    join = create_join_code(request.auth)
    return Status(
        200,
        JoinCodeOut(
            code=join.code,
            expires_at=join.expires_at,
            bot_name=_telegram_bot_name(),
        ),
    )
