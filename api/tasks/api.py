from __future__ import annotations

from uuid import UUID

from django.db import connection
from django.db.models import Count, QuerySet
from django.utils import timezone
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.http import AuthedHttpRequest
from accounts.schemas import ErrorOut
from accounts.models import User
from tasks.models import Task, TaskAuditLog, TaskStatus
from tasks.schemas import (
    StatusCountItem,
    TagCountItem,
    TaskAuditLogListOut,
    TaskAuditLogOut,
    TaskFacetsOut,
    TaskListOut,
    TaskOut,
)
from tasks.services import top_active_tags_for_user
from taskraptor.timezones import serialize_datetime_with_local

router = Router(tags=["tasks"], auth=AuthBearer())


def _base_queryset(user: User) -> QuerySet[Task]:
    return Task.objects.filter(
        user=user,
        deleted_at__isnull=True,
    )


def _to_task_out(task: Task, user: User) -> TaskOut:
    tags = task.tags if isinstance(task.tags, list) else []
    due_at = serialize_datetime_with_local(task.due_at, user.timezone)
    return TaskOut(
        id=task.id,
        name=task.name,
        status=task.status,
        priority=task.priority,
        due_at=task.due_at,
        due_at_local=due_at["local"],
        due_date_local=due_at["local_date"],
        due_type=task.due_type,
        timezone=due_at["timezone"] or user.timezone,
        tags=[str(t) for t in tags],
        remind_at=task.remind_at,
        completed_at=task.completed_at,
        archived_at=task.archived_at,
        created_at=task.created_at,
    )


def _to_task_audit_log_out(log: TaskAuditLog) -> TaskAuditLogOut:
    return TaskAuditLogOut(
        id=log.id,
        task_id=log.task_id,
        created_at=log.created_at,
        action=log.action,
        old_value=log.old_value,
        new_value=log.new_value,
        actor_id=log.actor_id,
    )


@router.get(
    "/facets",
    response={200: TaskFacetsOut, 401: ErrorOut},
)
def task_facets(request: AuthedHttpRequest):
    user = request.auth
    base = _base_queryset(user)

    total = base.count()

    status_qs = (
        base.values("status")
        .annotate(count=Count("id", distinct=True))
        .order_by("status")
    )
    status_counts = [
        StatusCountItem(status=row["status"], count=row["count"])
        for row in status_qs
    ]

    tag_counts = [
        TagCountItem(tag=tag, count=n)
        for tag, n in top_active_tags_for_user(user.pk)
    ]

    return Status(
        200,
        TaskFacetsOut(
            status_counts=status_counts,
            tag_counts=tag_counts,
            total=total,
        ),
    )


@router.get(
    "/",
    response={200: TaskListOut, 401: ErrorOut},
)
def list_tasks(
    request: AuthedHttpRequest,
    status: str | None = None,
    tag: str | None = None,
    upcoming: bool | None = None,
    priority: int | None = None,
    min_priority: int | None = None,
    max_priority: int | None = None,
):
    user = request.auth
    qs = _base_queryset(user)

    if status is not None and status != "":
        qs = qs.filter(status=status)

    if tag is not None and tag.strip() != "":
        t = tag.strip()
        if connection.features.supports_json_field_contains:
            qs = qs.filter(tags__contains=[t])
        else:
            # SQLite (tests): JSON `contains` for arrays is not supported; filter in Python
            match_ids: list[UUID] = [
                pk
                for pk, tag_list in qs.values_list("pk", "tags")
                if isinstance(tag_list, list) and t in (str(x) for x in tag_list)
            ]
            qs = qs.filter(pk__in=match_ids)

    if upcoming is True:
        now = timezone.now()
        qs = qs.filter(
            due_at__isnull=False,
            due_at__gte=now,
        ).exclude(status=TaskStatus.COMPLETED)

    if priority is not None:
        qs = qs.filter(priority=priority)
    else:
        if min_priority is not None:
            qs = qs.filter(priority__gte=min_priority)
        if max_priority is not None:
            qs = qs.filter(priority__lte=max_priority)

    tasks = list(qs)
    return Status(
        200,
        TaskListOut(
            tasks=[_to_task_out(t, user) for t in tasks],
            count=len(tasks),
        ),
    )


@router.get(
    "/{task_id}/audit-logs",
    response={200: TaskAuditLogListOut, 401: ErrorOut, 404: ErrorOut},
)
def get_task_audit_logs(request: AuthedHttpRequest, task_id: UUID):
    user = request.auth
    if not _base_queryset(user).filter(pk=task_id).exists():
        return Status(404, {"detail": "Not found."})

    logs = TaskAuditLog.objects.filter(task_id=task_id).order_by("-created_at")
    return Status(
        200,
        TaskAuditLogListOut(
            audit_logs=[_to_task_audit_log_out(log) for log in logs],
        ),
    )


@router.get(
    "/{task_id}",
    response={200: TaskOut, 401: ErrorOut, 404: ErrorOut},
)
def get_task(request: AuthedHttpRequest, task_id: UUID):
    user = request.auth
    try:
        task = _base_queryset(user).get(pk=task_id)
    except Task.DoesNotExist:
        return Status(404, {"detail": "Not found."})
    return Status(200, _to_task_out(task, user))
