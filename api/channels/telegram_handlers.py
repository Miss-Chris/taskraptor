from __future__ import annotations

import logging

from channels.services import get_conversation
from channels.telegram import (
    find_channel_by_telegram_chat_id,
    redeem_join_code,
    send_telegram_message,
)
from channels.telegram_media import (
    NoImageCapableModelError,
    UnsupportedTelegramAttachmentError,
    build_attachment_user_message,
)
from channels.workflow import NoActiveLlmModel, handle_user_incoming

logger = logging.getLogger(__name__)

JOIN_SUCCESS_MESSAGE = "You're connected to TaskRaptor. You can start chatting now."
JOIN_FAILURE_MESSAGE = "Something went wrong linking your account. Please try again later."
UNLINKED_CHAT_MESSAGE = "This chat is not linked to TaskRaptor. Use a join code from the app first."
NO_ACTIVE_MODEL_MESSAGE = (
    "I couldn't find an active AI model for your account. Open TaskRaptor, "
    "go to Models, and add or activate a model to keep chatting."
)
WORKFLOW_FAILURE_MESSAGE = "Something went wrong processing your message. Please try again later."
UNSUPPORTED_ATTACHMENT_MESSAGE = "I can currently read photos and UTF-8 text files."
NO_IMAGE_MODEL_MESSAGE = (
    "I can read images once an image-capable model is set up. Open TaskRaptor, "
    "go to Models, and add or activate a model with image support."
)


def safe_send_telegram_message(chat_id: str, text: str, *, log_context: str) -> bool:
    try:
        send_telegram_message(chat_id, text)
    except Exception:
        logger.exception(
            "telegram webhook: failed to send %s chat_id=%s",
            log_context,
            chat_id,
        )
        return False
    return True


def handle_telegram_join(chat_id: str, join_code: str) -> None:
    try:
        redeem_join_code(join_code, chat_id)
        safe_send_telegram_message(
            chat_id,
            JOIN_SUCCESS_MESSAGE,
            log_context="join success",
        )
    except ValueError as exc:
        safe_send_telegram_message(
            chat_id,
            str(exc),
            log_context="join validation error",
        )
    except Exception:
        logger.exception("telegram webhook: redeem_join_code failed chat_id=%s", chat_id)
        safe_send_telegram_message(
            chat_id,
            JOIN_FAILURE_MESSAGE,
            log_context="generic join error",
        )


def handle_telegram_text(chat_id: str, text: str) -> None:
    normalized_text = text.strip()
    if not normalized_text:
        return

    channel = None
    try:
        channel = find_channel_by_telegram_chat_id(chat_id)
        if channel is None:
            safe_send_telegram_message(
                chat_id,
                UNLINKED_CHAT_MESSAGE,
                log_context="unlink notice",
            )
            return

        runtime_conversation = get_conversation(channel.pk)
        handle_user_incoming(runtime_conversation.conversation, normalized_text)
    except NoActiveLlmModel:
        safe_send_telegram_message(
            chat_id,
            NO_ACTIVE_MODEL_MESSAGE,
            log_context="NoActiveLlmModel notice",
        )
    except Exception:
        logger.exception(
            "telegram webhook: text processing failed channel_id=%s",
            getattr(channel, "pk", None),
        )
        safe_send_telegram_message(
            chat_id,
            WORKFLOW_FAILURE_MESSAGE,
            log_context="text processing error",
        )


def handle_telegram_attachment(
    chat_id: str,
    attachment_kind: str,
    file_id: str,
    *,
    caption: str = "",
    file_name: str = "",
    mime_type: str = "",
) -> None:
    channel = None
    try:
        channel = find_channel_by_telegram_chat_id(chat_id)
        if channel is None:
            safe_send_telegram_message(
                chat_id,
                UNLINKED_CHAT_MESSAGE,
                log_context="unlink notice",
            )
            return

        message = build_attachment_user_message(
            channel.user,
            attachment_kind=attachment_kind,
            file_id=file_id,
            caption=caption,
            file_name=file_name,
            mime_type=mime_type,
        )
    except UnsupportedTelegramAttachmentError:
        safe_send_telegram_message(
            chat_id,
            UNSUPPORTED_ATTACHMENT_MESSAGE,
            log_context="unsupported attachment notice",
        )
        return
    except NoImageCapableModelError:
        safe_send_telegram_message(
            chat_id,
            NO_IMAGE_MODEL_MESSAGE,
            log_context="no image-capable model notice",
        )
        return
    except Exception:
        logger.exception(
            "telegram webhook: attachment conversion failed channel_id=%s",
            getattr(channel, "pk", None),
        )
        safe_send_telegram_message(
            chat_id,
            WORKFLOW_FAILURE_MESSAGE,
            log_context="attachment conversion error",
        )
        return

    try:
        runtime_conversation = get_conversation(channel.pk)
        handle_user_incoming(runtime_conversation.conversation, message)
    except NoActiveLlmModel:
        safe_send_telegram_message(
            chat_id,
            NO_ACTIVE_MODEL_MESSAGE,
            log_context="NoActiveLlmModel notice",
        )
    except Exception:
        logger.exception(
            "telegram webhook: attachment processing failed channel_id=%s",
            getattr(channel, "pk", None),
        )
        safe_send_telegram_message(
            chat_id,
            WORKFLOW_FAILURE_MESSAGE,
            log_context="attachment processing error",
        )
