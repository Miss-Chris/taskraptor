from __future__ import annotations

import logging

from channels.services import get_conversation
from channels.telegram import (
    find_channel_by_telegram_chat_id,
    redeem_join_code,
    send_telegram_message,
)
from channels.workflow import NoActiveLlmModel, handle_user_incoming

logger = logging.getLogger(__name__)

JOIN_SUCCESS_MESSAGE = "You're connected to TaskRaptor. You can start chatting now."
JOIN_FAILURE_MESSAGE = "Something went wrong linking your account. Please try again later."
UNLINKED_CHAT_MESSAGE = "This chat is not linked to TaskRaptor. Use a join code from the app first."
NO_ACTIVE_MODEL_MESSAGE = (
    "No active AI model is configured for your account. Please add one in TaskRaptor."
)
WORKFLOW_FAILURE_MESSAGE = "Something went wrong processing your message. Please try again later."


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

    channel = find_channel_by_telegram_chat_id(chat_id)
    if channel is None:
        safe_send_telegram_message(
            chat_id,
            UNLINKED_CHAT_MESSAGE,
            log_context="unlink notice",
        )
        return

    runtime_conversation = get_conversation(channel.pk)
    try:
        handle_user_incoming(runtime_conversation.conversation, normalized_text)
    except NoActiveLlmModel:
        safe_send_telegram_message(
            chat_id,
            NO_ACTIVE_MODEL_MESSAGE,
            log_context="NoActiveLlmModel notice",
        )
    except Exception:
        logger.exception(
            "telegram webhook: handle_user_incoming failed channel_id=%s",
            channel.pk,
        )
        safe_send_telegram_message(
            chat_id,
            WORKFLOW_FAILURE_MESSAGE,
            log_context="workflow error",
        )
