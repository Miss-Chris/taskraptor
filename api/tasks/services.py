from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone

from tasks.models import AuditAction, Task, TaskAuditLog, TaskStatus

UNSET = object()


def create_task(
    *,
    user_id: int,
    name: str,
    status: str = TaskStatus.PENDING,
    priority: int = 0,
    due_at: datetime | None = None,
    tags: list[str] | None = None,
) -> Task:
    completed_at = timezone.now() if status == TaskStatus.COMPLETED else None
    return Task.objects.create(
        user_id=user_id,
        name=name,
        status=status,
        priority=priority,
        due_at=due_at,
        tags=tags or [],
        completed_at=completed_at,
    )


def update_task(
    task: Task,
    *,
    audit_actor_id: int | None = None,
    name: Any = UNSET,
    status: Any = UNSET,
    priority: Any = UNSET,
    due_at: Any = UNSET,
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
        task.due_at = due_at
        update_fields.append("due_at")
    elif clear_due_at:
        task.due_at = None
        update_fields.append("due_at")

    if tags is not UNSET:
        task.tags = tags
        update_fields.append("tags")

    if update_fields:
        task.save(
            update_fields=list(dict.fromkeys(update_fields)),
            audit_actor_id=audit_actor_id,
        )

    return update_fields


def soft_delete_task(task: Task, *, audit_actor_id: int | None = None) -> None:
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
