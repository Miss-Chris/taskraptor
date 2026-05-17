from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from tasks.models import Task, TaskStatus
from tasks.reminders import run_task_reminder_on_active_channels

logger = logging.getLogger(__name__)


def _get_user_timezone(timezone_name: str | None) -> ZoneInfo | None:
    if not timezone_name:
        return None
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning("[tasks] invalid timezone=%r, defaulting to UTC", timezone_name)
        return ZoneInfo("UTC")


def task_reminder_is_due(task: Task, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    if task.user.timezone is None or _get_user_timezone(task.user.timezone) is None:
        logger.info("[tasks] skipping task reminder=%s without timezone", task.pk)
        return False
    return (
        task.deleted_at is None
        and task.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
        and task.remind_at is not None
        and task.reminded_at is None
        and task.remind_at <= now
    )


@shared_task(name="tasks.dispatch_due_task_reminders")
def dispatch_due_task_reminders() -> int:
    now = timezone.now()
    queued = 0
    tasks = (
        Task.objects.filter(
            deleted_at__isnull=True,
            remind_at__isnull=False,
            reminded_at__isnull=True,
        )
        .exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        .select_related("user")
        .iterator()
    )
    for task in tasks:
        if not task_reminder_is_due(task, now=now):
            continue
        run_task_reminder.delay(str(task.pk))
        queued += 1
    return queued


@shared_task(name="tasks.run_task_reminder")
def run_task_reminder(task_id: str | UUID) -> bool:
    with transaction.atomic():
        task = (
            Task.objects.select_for_update()
            .select_related("user")
            .filter(pk=task_id)
            .first()
        )
        if task is None or not task_reminder_is_due(task):
            return False
        run_task_reminder_on_active_channels(task)
        task.reminded_at = timezone.now()
        task.save(update_fields=["reminded_at"])
    return True
