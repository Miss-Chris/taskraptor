from __future__ import annotations

import base64
from pathlib import Path
from typing import Callable

from agent.llm import call_llm
from agent.models import LlmModel
from channels.telegram import download_telegram_file

TEXT_ATTACHMENT_MAX_BYTES = 256_000
TEXT_ATTACHMENT_MAX_CHARS = 20_000
TEXT_FILE_SUFFIXES = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILE_MIME_TYPES = {
    "application/json",
    "application/x-yaml",
}


class UnsupportedTelegramAttachmentError(Exception):
    """Raised when a Telegram attachment is outside the v1 supported set."""


class NoImageCapableModelError(Exception):
    """Raised when a user has no configured model that can read images."""


def _is_supported_text_document(file_name: str, mime_type: str) -> bool:
    suffix = Path(file_name or "").suffix.lower()
    normalized_mime = (mime_type or "").lower()
    return (
        normalized_mime.startswith("text/")
        or normalized_mime in TEXT_FILE_MIME_TYPES
        or suffix in TEXT_FILE_SUFFIXES
    )


def _decode_text_document(file_bytes: bytes) -> str:
    if len(file_bytes) > TEXT_ATTACHMENT_MAX_BYTES:
        raise UnsupportedTelegramAttachmentError(
            f"Text attachments must be {TEXT_ATTACHMENT_MAX_BYTES // 1000} KB or smaller.",
        )
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnsupportedTelegramAttachmentError(
            "Text attachments must be UTF-8 encoded.",
        ) from exc
    normalized = text.strip()
    if not normalized:
        raise UnsupportedTelegramAttachmentError("Text attachment was empty.")
    if len(normalized) > TEXT_ATTACHMENT_MAX_CHARS:
        normalized = (
            normalized[:TEXT_ATTACHMENT_MAX_CHARS].rstrip()
            + "\n\n[attachment truncated]"
        )
    return normalized


def _image_capable_model_for_user(user) -> LlmModel:
    models = LlmModel.objects.filter(user=user).order_by("-is_active", "-created_at")
    for model in models:
        if model.supports_image_input and (model.api_key or "").strip():
            return model
    raise NoImageCapableModelError(
        "No configured image-capable model is available for this account.",
    )


def _image_data_url(image_bytes: bytes, mime_type: str) -> str:
    safe_mime_type = mime_type or "image/jpeg"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{safe_mime_type};base64,{encoded}"


def _describe_image(
    user,
    image_bytes: bytes,
    mime_type: str,
    *,
    llm_callable: Callable | None = None,
) -> str:
    model = _image_capable_model_for_user(user)
    _call = llm_callable or call_llm
    response = _call(
        model,
        [
            {
                "role": "system",
                "content": (
                    "Convert Telegram image attachments into plain text for a downstream "
                    "text-only assistant. Describe the visible content concisely, preserve "
                    "important text when legible, and return only the converted text."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Convert this image into useful plain text.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_data_url(image_bytes, mime_type)},
                    },
                ],
            },
        ],
        max_tokens=800,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("Image-capable model returned an empty description.")
    return content


def build_attachment_user_message(
    user,
    *,
    attachment_kind: str,
    file_id: str,
    caption: str = "",
    file_name: str = "",
    mime_type: str = "",
    llm_callable: Callable | None = None,
) -> str:
    file_bytes = download_telegram_file(file_id)
    normalized_caption = caption.strip()

    if attachment_kind == "photo":
        converted = _describe_image(
            user,
            file_bytes,
            mime_type or "image/jpeg",
            llm_callable=llm_callable,
        )
        parts = ["[Telegram image attachment]"]
        if normalized_caption:
            parts.append(f"Caption: {normalized_caption}")
        parts.append(f"Converted image content:\n{converted}")
        return "\n\n".join(parts)

    if attachment_kind == "document" and _is_supported_text_document(file_name, mime_type):
        text = _decode_text_document(file_bytes)
        parts = [f"[Telegram text attachment: {file_name or 'document'}]"]
        if normalized_caption:
            parts.append(f"Caption: {normalized_caption}")
        parts.append(f"Contents:\n{text}")
        return "\n\n".join(parts)

    raise UnsupportedTelegramAttachmentError(
        "Only photos and UTF-8 text documents are supported right now.",
    )
