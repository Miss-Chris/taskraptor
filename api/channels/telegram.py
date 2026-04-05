from __future__ import annotations

import json
import logging
import secrets
import string
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from channels.models import Channel, ChannelType, TelegramJoinCode

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
        .order_by("-pk")
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


def send_telegram_message(chat_id: str, text: str) -> dict:
    """
    Call Telegram Bot API ``sendMessage``. Returns the parsed JSON response.

    Raises ``RuntimeError`` on HTTP errors or Telegram ``ok: false`` responses.
    """
    payload = json.dumps(
        {"chat_id": chat_id, "text": text},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        _telegram_api_url("sendMessage"),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.exception(
            "Telegram sendMessage HTTP error status=%s body=%s", exc.code, body
        )
        raise RuntimeError(f"Telegram API HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        logger.exception("Telegram sendMessage network error")
        raise RuntimeError(f"Telegram API network error: {exc}") from exc

    data = json.loads(raw)
    if not data.get("ok"):
        desc = data.get("description", raw)
        logger.error("Telegram sendMessage failed: %s", desc)
        raise RuntimeError(f"Telegram API error: {desc}")
    return data


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
    payload = json.dumps({"url": webhook_url}).encode("utf-8")
    req = urllib.request.Request(
        _telegram_api_url("setWebhook"),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.exception(
            "Telegram setWebhook HTTP error status=%s body=%s", exc.code, body
        )
        raise RuntimeError(f"Telegram setWebhook HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        logger.exception("Telegram setWebhook network error")
        raise RuntimeError(f"Telegram setWebhook network error: {exc}") from exc

    data = json.loads(raw)
    if not data.get("ok"):
        desc = data.get("description", raw)
        logger.error("Telegram setWebhook failed: %s", desc)
        raise RuntimeError(f"Telegram setWebhook error: {desc}")
    return data


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
