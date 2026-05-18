from __future__ import annotations

import logging
from collections.abc import Iterable

from accounts.models import User
from channels.models import Channel
from channels.services import get_conversation
from channels.web import get_or_create_default_web_channel
from channels.workflow import handle_system_message
from tasks.models import Task

logger = logging.getLogger(__name__)


def build_task_reminder_prompt(task: Task) -> str:
    return (
        "This is a system-triggered reminder delivery for an existing task. "
        "Notify the user now in one brief message. "
        "Do not create, edit, clear, or reschedule any task or reminder. "
        f"Task: {task.name}"
    )


def active_task_reminder_channels(user: User) -> Iterable[Channel]:
    get_or_create_default_web_channel(user)
    return (
        Channel.objects.filter(user=user, archived_at__isnull=True)
        .order_by("created_at", "id")
        .select_related("user")
    )


def run_task_reminder_on_active_channels(task: Task) -> int:
    count = 0
    prompt = build_task_reminder_prompt(task)
    for channel in active_task_reminder_channels(task.user):
        get_conversation(channel.pk)
        handle_system_message(channel, prompt)
        count += 1
    logger.info(
        "[tasks] ran reminder task_id=%s user_id=%s channel_count=%s",
        task.pk,
        task.user_id,
        count,
    )
    return count
