import json
from urllib import error, request

from django.conf import settings


class TelegramConfigurationError(Exception):
    pass


class TelegramApiError(Exception):
    pass


TELEGRAM_WEBHOOK_PATH = "/api/channels/telegram/webhook"


def get_telegram_bot_token() -> str:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is not configured")
    return token


def get_telegram_webhook_url() -> str:
    base_url = settings.TELEGRAM_WEBHOOK_BASE_URL.strip()
    if not base_url:
        raise TelegramConfigurationError("TELEGRAM_WEBHOOK_BASE_URL is not configured")
    return f"{base_url.rstrip('/')}{TELEGRAM_WEBHOOK_PATH}"


def telegram_api_request(method: str, payload: dict) -> dict:
    token = get_telegram_bot_token()
    endpoint = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise TelegramApiError(f"Telegram API request failed: {detail}") from exc
    except error.URLError as exc:
        raise TelegramApiError(f"Telegram API request failed: {exc.reason}") from exc

    if not body.get("ok"):
        raise TelegramApiError(f"Telegram API request failed: {body}")
    return body


def set_telegram_webhook() -> dict:
    return telegram_api_request("setWebhook", {"url": get_telegram_webhook_url()})


def send_telegram_message(chat_id: int, text: str) -> dict:
    return telegram_api_request("sendMessage", {"chat_id": chat_id, "text": text})
