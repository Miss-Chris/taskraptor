from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any
from uuid import UUID

from django.utils import timezone

from accounts.models import User
from tasks.models import AuditAction, DueType, Task, TaskAuditLog, TaskStatus, UserTag
from taskraptor.timezones import normalize_to_utc

UNSET = object()


def top_active_tags_for_user(
    user_id: UUID,
    *,
    limit: int | None = None,
) -> list[tuple[str, int]]:
    qs = Task.objects.filter(
        user_id=user_id,
        deleted_at__isnull=True,
        archived_at__isnull=True,
    ).exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED])

    tag_counter: Counter[str] = Counter()
    for tags in qs.values_list("tags", flat=True):
        if isinstance(tags, list):
            for raw_tag in tags:
                tag = str(raw_tag).strip()
                if tag:
                    tag_counter[tag] += 1

    ranked = sorted(tag_counter.items(), key=lambda item: (-item[1], item[0]))
    seen = {tag for tag, _count in ranked}
    catalog_tags = UserTag.objects.filter(user_id=user_id).order_by(
        "sort_order",
        "name",
    )
    for user_tag in catalog_tags:
        tag = user_tag.name.strip()
        if tag and tag not in seen:
            ranked.append((tag, 0))
            seen.add(tag)

    if limit is None:
        return ranked
    return ranked[:limit]


def create_task(
    *,
    user_id: UUID,
    name: str,
    status: str = TaskStatus.PENDING,
    priority: int = 0,
    due_at: datetime | None = None,
    due_type: str = DueType.TIME,
    tags: list[str] | None = None,
) -> Task:
    if due_at is not None:
        user_timezone = User.objects.values_list("timezone", flat=True).get(pk=user_id)
        due_at = normalize_due_at_for_user(due_at, user_timezone)

    completed_at = timezone.now() if status == TaskStatus.COMPLETED else None
    return Task.objects.create(
        user_id=user_id,
        name=name,
        status=status,
        priority=priority,
        due_at=due_at,
        due_type=due_type,
        tags=tags or [],
        completed_at=completed_at,
    )


def normalize_due_at_for_user(
    due_at: datetime | None,
    user_timezone: str | None,
) -> datetime | None:
    if due_at is None:
        return None
    return normalize_to_utc(due_at, user_timezone)


def update_task(
    task: Task,
    *,
    audit_actor_id: UUID | None = None,
    name: Any = UNSET,
    status: Any = UNSET,
    priority: Any = UNSET,
    due_at: Any = UNSET,
    due_type: Any = UNSET,
    tags: Any = UNSET,
    clear_due_at: bool = False,
) -> list[str]:
    if clear_due_at and due_at is not UNSET and due_at is not None:
        raise ValueError("Cannot set due_at and clear_due_at in the same update.")

    update_fields: list[str] = []

    if name is not UNSET:
        task.name = name
        update_fields.append("name")

    if status is not UNSET:
        previous_status = task.status
        task.status = status
        update_fields.append("status")
        if status == TaskStatus.COMPLETED and previous_status != TaskStatus.COMPLETED:
            task.completed_at = timezone.now()
            update_fields.append("completed_at")
        elif status != TaskStatus.COMPLETED and previous_status == TaskStatus.COMPLETED:
            task.completed_at = None
            update_fields.append("completed_at")

    if priority is not UNSET:
        task.priority = priority
        update_fields.append("priority")

    if due_at is not UNSET:
        task.due_at = normalize_due_at_for_user(due_at, task.user.timezone)
        update_fields.append("due_at")
    elif clear_due_at:
        task.due_at = None
        update_fields.append("due_at")

    if due_type is not UNSET:
        task.due_type = due_type
        update_fields.append("due_type")

    if tags is not UNSET:
        task.tags = tags
        update_fields.append("tags")

    if update_fields:
        task.save(
            update_fields=list(dict.fromkeys(update_fields)),
            audit_actor_id=audit_actor_id,
        )

    return update_fields


def soft_delete_task(task: Task, *, audit_actor_id: UUID | None = None) -> None:
    if task.deleted_at is not None:
        raise ValueError(f"Task {task.pk} is already deleted.")

    task.deleted_at = timezone.now()
    task.save(update_fields=["deleted_at"])
    TaskAuditLog.objects.create(
        task=task,
        action=AuditAction.DELETED,
        old_value={"deleted_at": None},
        new_value={"deleted_at": task.deleted_at.isoformat()},
        actor_id=audit_actor_id,
    )
