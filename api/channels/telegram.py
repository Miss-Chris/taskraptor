from __future__ import annotations

import logging
import secrets
import string
from datetime import timedelta

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from channels.models import Channel, ChannelType, TelegramJoinCode
from channels.telegram_format import markdown_to_telegram_html

logger = logging.getLogger(__name__)

JOIN_CODE_LENGTH = 6
JOIN_CODE_TTL = timedelta(minutes=15)
_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_join_code_string() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


def create_join_code(user) -> TelegramJoinCode:
    """
    Create a new join code for the user. Any prior unredeemed codes for this user
    are invalidated by setting their ``expires_at`` to now.
    """
    with transaction.atomic():
        now = timezone.now()
        TelegramJoinCode.objects.filter(user=user, redeemed_at__isnull=True).update(
            expires_at=now
        )
        for _ in range(256):
            code = _generate_join_code_string()
            if not TelegramJoinCode.objects.filter(code=code).exists():
                return TelegramJoinCode.objects.create(
                    user=user,
                    code=code,
                    expires_at=now + JOIN_CODE_TTL,
                )
        raise RuntimeError("Could not allocate a unique Telegram join code")


def get_active_telegram_channel(user) -> Channel | None:
    """Return the user's non-archived Telegram channel, if any."""
    return (
        Channel.objects.filter(
            user=user,
            type=ChannelType.TELEGRAM,
            archived_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )


def archive_telegram_channel(user) -> bool:
    """
    Mark the user's active Telegram channel as archived. Returns whether a row
    was updated.
    """
    now = timezone.now()
    updated = Channel.objects.filter(
        user=user,
        type=ChannelType.TELEGRAM,
        archived_at__isnull=True,
    ).update(archived_at=now)
    return updated > 0


def redeem_join_code(code: str, telegram_chat_id: str) -> Channel:
    """
    Redeem a join code, linking ``telegram_chat_id`` to the owning user.

    Raises ``ValueError`` if the code is missing, already used, or expired.
    """
    normalized = code.strip().upper()
    if len(normalized) != JOIN_CODE_LENGTH:
        raise ValueError("Invalid join code.")

    with transaction.atomic():
        try:
            join = TelegramJoinCode.objects.select_for_update().get(code=normalized)
        except TelegramJoinCode.DoesNotExist as exc:
            raise ValueError("Invalid join code.") from exc

        if join.redeemed_at is not None:
            raise ValueError("This join code has already been used.")

        now = timezone.now()
        if join.expires_at < now:
            raise ValueError("This join code has expired.")

        user = join.user
        archive_telegram_channel(user)

        channel = Channel.objects.create(
            user=user,
            name="Telegram",
            type=ChannelType.TELEGRAM,
            external_id=str(telegram_chat_id),
        )

        join.redeemed_at = now
        join.telegram_chat_id = str(telegram_chat_id)
        join.save(update_fields=["redeemed_at", "telegram_chat_id"])

        return channel


def _telegram_api_url(method: str) -> str:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
    return f"https://api.telegram.org/bot{token}/{method}"


def _post_telegram_json(method: str, payload: dict, *, log_context: str) -> dict:
    try:
        response = httpx.post(
            _telegram_api_url(method),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.exception(
            "Telegram %s HTTP error status=%s body=%s",
            log_context,
            exc.response.status_code,
            exc.response.text,
        )
        raise RuntimeError(
            f"Telegram {log_context} HTTP error: {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Telegram %s network error", log_context)
        raise RuntimeError(f"Telegram {log_context} network error: {exc}") from exc

    data = response.json()
    if not data.get("ok"):
        desc = data.get("description", response.text)
        logger.error("Telegram %s failed: %s", log_context, desc)
        raise RuntimeError(f"Telegram {log_context} error: {desc}")
    return data


def send_telegram_message(chat_id: str, text: str) -> dict:
    """
    Call Telegram Bot API ``sendMessage``. Returns the parsed JSON response.

    Raises ``RuntimeError`` on HTTP errors or Telegram ``ok: false`` responses.
    """
    return _post_telegram_json(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": markdown_to_telegram_html(text),
            "parse_mode": "HTML",
        },
        log_context="sendMessage",
    )


def get_telegram_file(file_id: str) -> dict:
    """
    Call Telegram Bot API ``getFile`` and return the result payload.

    Raises ``RuntimeError`` on HTTP errors or Telegram ``ok: false`` responses.
    """
    data = _post_telegram_json(
        "getFile",
        {"file_id": file_id},
        log_context="getFile",
    )
    result = data.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Telegram getFile response did not include a result object.")
    return result


def download_telegram_file(file_id: str) -> bytes:
    """
    Download a Telegram file by ``file_id`` using ``getFile`` metadata.
    """
    result = get_telegram_file(file_id)
    file_path = result.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        raise RuntimeError("Telegram getFile response did not include file_path.")

    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
    try:
        response = httpx.get(
            f"https://api.telegram.org/file/bot{token}/{file_path}",
            timeout=30,
        )
        response.raise_for_status()
        return response.content
    except httpx.HTTPStatusError as exc:
        logger.exception(
            "Telegram file download HTTP error status=%s body=%s",
            exc.response.status_code,
            exc.response.text,
        )
        raise RuntimeError(
            f"Telegram file download HTTP error: {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Telegram file download network error")
        raise RuntimeError(f"Telegram file download network error: {exc}") from exc


def set_telegram_webhook() -> dict:
    """
    Register the app webhook URL with Telegram (``setWebhook``).

    Webhook URL: ``{TELEGRAM_WEBHOOK_BASE_URL}/api/telegram/webhook`` (matches Ninja route).

    Returns the parsed JSON response. Raises ``RuntimeError`` if misconfigured.
    """
    base = (settings.TELEGRAM_WEBHOOK_BASE_URL or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("TELEGRAM_WEBHOOK_BASE_URL is not configured.")

    webhook_url = f"{base}/api/telegram/webhook"
    payload_data = {"url": webhook_url}
    secret_token = (getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "") or "").strip()
    if secret_token:
        payload_data["secret_token"] = secret_token

    return _post_telegram_json(
        "setWebhook",
        payload_data,
        log_context="setWebhook",
    )


def find_channel_by_telegram_chat_id(telegram_chat_id: str) -> Channel | None:
    """Resolve an active Telegram channel by Telegram ``chat.id`` string."""
    cid = str(telegram_chat_id)
    return (
        Channel.objects.filter(
            type=ChannelType.TELEGRAM,
            external_id=cid,
            archived_at__isnull=True,
        )
        .select_related("user")
        .first()
    )
