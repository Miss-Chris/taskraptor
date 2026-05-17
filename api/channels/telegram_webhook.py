from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

TelegramWebhookAction = Literal["ignore", "join", "text", "attachment"]

_JOIN_RE = re.compile(r"^\s*JOIN\s+([A-Za-z0-9]{6})\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class TelegramWebhookEvent:
    action: TelegramWebhookAction
    chat_id: str | None = None
    text: str = ""
    join_code: str | None = None
    attachment_kind: str | None = None
    file_id: str | None = None
    file_name: str = ""
    mime_type: str = ""
    caption: str = ""


IGNORE_EVENT = TelegramWebhookEvent(action="ignore")


def parse_telegram_webhook_body(raw_body: bytes | str | None) -> TelegramWebhookEvent:
    if raw_body in (None, b"", ""):
        return IGNORE_EVENT

    try:
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode("utf-8")
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return IGNORE_EVENT

    if not isinstance(payload, dict):
        return IGNORE_EVENT

    return route_telegram_update(payload)


def route_telegram_update(payload: Mapping[str, Any]) -> TelegramWebhookEvent:
    message = payload.get("message") or payload.get("edited_message")
    if not isinstance(message, Mapping):
        return IGNORE_EVENT

    chat = message.get("chat")
    if not isinstance(chat, Mapping):
        return IGNORE_EVENT

    chat_id = chat.get("id")
    if chat_id is None:
        return IGNORE_EVENT

    caption = message.get("caption")
    normalized_caption = caption.strip() if isinstance(caption, str) else ""

    photo = message.get("photo")
    if isinstance(photo, list):
        photo_sizes = [
            item
            for item in photo
            if isinstance(item, Mapping) and isinstance(item.get("file_id"), str)
        ]
        if photo_sizes:
            chosen = max(
                photo_sizes,
                key=lambda item: (
                    item.get("file_size") or 0,
                    item.get("width") or 0,
                    item.get("height") or 0,
                ),
            )
            return TelegramWebhookEvent(
                action="attachment",
                chat_id=str(chat_id),
                attachment_kind="photo",
                file_id=chosen["file_id"],
                mime_type="image/jpeg",
                caption=normalized_caption,
            )

    document = message.get("document")
    if isinstance(document, Mapping) and isinstance(document.get("file_id"), str):
        return TelegramWebhookEvent(
            action="attachment",
            chat_id=str(chat_id),
            attachment_kind="document",
            file_id=document["file_id"],
            file_name=str(document.get("file_name") or ""),
            mime_type=str(document.get("mime_type") or ""),
            caption=normalized_caption,
        )

    text = message.get("text")
    if not isinstance(text, str):
        return IGNORE_EVENT

    normalized_text = text.strip()
    if not normalized_text:
        return IGNORE_EVENT

    match = _JOIN_RE.match(normalized_text)
    if match:
        return TelegramWebhookEvent(
            action="join",
            chat_id=str(chat_id),
            text=normalized_text,
            join_code=match.group(1).upper(),
        )

    return TelegramWebhookEvent(
        action="text",
        chat_id=str(chat_id),
        text=normalized_text,
    )
