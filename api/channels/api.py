from __future__ import annotations

import logging

from django.http import HttpRequest, JsonResponse
from ninja import Router

from channels.tasks import process_telegram_join, process_telegram_text
from channels.telegram import set_telegram_webhook
from channels.telegram_webhook import parse_telegram_webhook_body

logger = logging.getLogger(__name__)

router = Router(tags=["telegram"])

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
