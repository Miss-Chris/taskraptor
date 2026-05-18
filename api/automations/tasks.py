from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from automations.models import Automation
from automations.services import run_automation_on_active_channels

logger = logging.getLogger(__name__)


def _get_user_timezone(timezone_name: str | None) -> ZoneInfo | None:
    if not timezone_name:
        return None
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning(
            "[automations] invalid timezone=%r, defaulting to UTC",
            timezone_name,
        )
        return ZoneInfo("UTC")


def automation_is_due(automation: Automation, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    user_timezone = _get_user_timezone(automation.user.timezone)
    if user_timezone is None:
        logger.info(
            "[automations] skipping automation=%s for user=%s without timezone",
            automation.pk,
            automation.user_id,
        )
        return False
    local_now = timezone.localtime(now, user_timezone)

    if local_now.time() < automation.schedule_time:
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
        .select_related("user")
        .iterator()
    )
    for automation in automations:
        if not automation_is_due(automation, now=now):
            continue
        run_automation.delay(str(automation.pk))
        queued += 1

    logger.info("[automations] dispatched due automations queued=%s", queued)
    return queued


@shared_task(name="automations.run_automation")
def run_automation(automation_id: str | UUID) -> bool:
    with transaction.atomic():
        automation = (
            Automation.objects.select_for_update()
            .select_related("user")
            .filter(pk=automation_id, is_active=True)
            .first()
        )
        if automation is None:
            return False

        now = timezone.now()
        if not automation_is_due(automation, now=now):
            return False

        # Keep the due-check, fan-out, and last_run_at write under the same row
        # lock so overlapping beat ticks do not double-run the same automation.
        # TODO: long agent runs hold this lock; a later claim/complete state
        # should release the transaction before executing channel fan-out.
        run_automation_on_active_channels(automation)
        automation.last_run_at = now
        automation.save(update_fields=["last_run_at", "updated_at"])

    return True


@shared_task(name="automations.run_automation_immediately")
def run_automation_immediately(automation_id: str | UUID) -> bool:
    automation = (
        Automation.objects.select_related("user")
        .filter(pk=automation_id)
        .first()
    )
    if automation is None:
        return False

    run_automation_on_active_channels(automation)
    automation.last_run_at = timezone.now()
    automation.save(update_fields=["last_run_at", "updated_at"])
    return True
