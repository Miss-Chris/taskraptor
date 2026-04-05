from __future__ import annotations

from celery import shared_task

from channels.telegram_handlers import handle_telegram_join, handle_telegram_text


@shared_task(name="channels.process_telegram_join")
def process_telegram_join(chat_id: str, join_code: str) -> None:
    handle_telegram_join(str(chat_id), str(join_code))


@shared_task(name="channels.process_telegram_text")
def process_telegram_text(chat_id: str, text: str) -> None:
    handle_telegram_text(str(chat_id), str(text))
