from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from automations.models import Automation
from channels.workflow import handle_system_message

logger = logging.getLogger(__name__)


def _get_user_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning(
            "[automations] invalid timezone=%r, defaulting to UTC",
            timezone_name,
        )
        return ZoneInfo("UTC")


def _scheduled_at_for_local_day(automation: Automation, local_now: datetime) -> datetime:
    schedule_time = automation.schedule_time
    return local_now.replace(
        hour=schedule_time.hour,
        minute=schedule_time.minute,
        second=schedule_time.second,
        microsecond=schedule_time.microsecond,
    )


def automation_is_due(automation: Automation, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    user_timezone = _get_user_timezone(automation.user.timezone)
    local_now = timezone.localtime(now, user_timezone)
    scheduled_at = _scheduled_at_for_local_day(automation, local_now)

    if local_now < scheduled_at:
        return False

    if automation.last_run_at is None:
        return True

    last_run_local = timezone.localtime(automation.last_run_at, user_timezone)
    return last_run_local.date() < local_now.date()


@shared_task(name="automations.dispatch_due_automations")
def dispatch_due_automations() -> int:
    now = timezone.now()
    queued = 0

    automations = (
        Automation.objects.filter(is_active=True)
        .select_related("user", "channel")
        .iterator()
    )
    for automation in automations:
        if not automation_is_due(automation, now=now):
            continue
        run_automation.delay(str(automation.pk))
        queued += 1

    return queued


@shared_task(name="automations.run_automation")
def run_automation(automation_id: str | UUID) -> bool:
    with transaction.atomic():
        automation = (
            Automation.objects.select_for_update()
            .select_related("user", "channel")
            .filter(pk=automation_id, is_active=True)
            .first()
        )
        if automation is None:
            return False

        now = timezone.now()
        if not automation_is_due(automation, now=now):
            return False

        # Keep the due-check and last_run_at write under the same row lock so
        # overlapping beat ticks do not double-run the same automation.
        handle_system_message(automation.channel, automation.prompt)
        automation.last_run_at = now
        automation.save(update_fields=["last_run_at", "updated_at"])

    return True
