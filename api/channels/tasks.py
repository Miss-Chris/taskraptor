from __future__ import annotations

from celery import shared_task

from channels.telegram_handlers import (
    handle_telegram_attachment,
    handle_telegram_join,
    handle_telegram_text,
)
from channels.web import process_next_pending_web_message


@shared_task(name="channels.process_telegram_join")
def process_telegram_join(chat_id: str, join_code: str) -> None:
    handle_telegram_join(str(chat_id), str(join_code))


@shared_task(name="channels.process_telegram_text")
def process_telegram_text(chat_id: str, text: str) -> None:
    handle_telegram_text(str(chat_id), str(text))


@shared_task(name="channels.process_telegram_attachment")
def process_telegram_attachment(
    chat_id: str,
    attachment_kind: str,
    file_id: str,
    caption: str = "",
    file_name: str = "",
    mime_type: str = "",
) -> None:
    handle_telegram_attachment(
        str(chat_id),
        str(attachment_kind),
        str(file_id),
        caption=str(caption),
        file_name=str(file_name),
        mime_type=str(mime_type),
    )


@shared_task(name="channels.process_web_message")
def process_web_message(conversation_id: str, message_id: str, agent_run_id: str) -> None:
    # message_id and agent_run_id are included for traceability. Processing always
    # selects the oldest pending run for the conversation to preserve send order.
    process_next_pending_web_message(conversation_id)
