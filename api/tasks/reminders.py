from __future__ import annotations

from collections.abc import Iterable

from accounts.models import User
from channels.models import Channel
from channels.services import get_conversation
from channels.web import get_or_create_default_web_channel
from channels.workflow import handle_system_message
from tasks.models import Task


def active_task_reminder_channels(user: User) -> Iterable[Channel]:
    get_or_create_default_web_channel(user)
    return (
        Channel.objects.filter(user=user, archived_at__isnull=True)
        .order_by("created_at", "id")
        .select_related("user")
    )


def run_task_reminder_on_active_channels(task: Task) -> int:
    count = 0
    prompt = f"Remind the user about this task now: {task.name}"
    for channel in active_task_reminder_channels(task.user):
        get_conversation(channel.pk)
        handle_system_message(channel, prompt)
        count += 1
    return count
