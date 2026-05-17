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
    TaskCreateIn,
    TaskFacetsOut,
    TaskListOut,
    TaskOut,
    TaskUpdateIn,
)
from tasks.services import (
    UNSET,
    create_task,
    soft_delete_task,
    top_active_tags_for_user,
    update_task,
)
from taskraptor.timezones import parse_user_datetime, serialize_datetime_with_local

router = Router(tags=["tasks"], auth=AuthBearer())


def _base_queryset(user: User) -> QuerySet[Task]:
    return Task.objects.filter(
        user=user,
        deleted_at__isnull=True,
    )


def _to_task_out(task: Task, user: User) -> TaskOut:
    tags = task.tags if isinstance(task.tags, list) else []
    due_at = serialize_datetime_with_local(task.due_at, user.timezone)
    remind_at = serialize_datetime_with_local(task.remind_at, user.timezone)
    return TaskOut(
        id=task.id,
        name=task.name,
        description=task.description,
        agent_notes=task.agent_notes,
        status=task.status,
        priority=task.priority,
        due_at=task.due_at,
        due_at_local=due_at["local"],
        due_date_local=due_at["local_date"],
        due_type=task.due_type,
        timezone=due_at["timezone"] or user.timezone,
        tags=[str(t) for t in tags],
        remind_at=task.remind_at,
        remind_at_local=remind_at["local"],
        remind_date_local=remind_at["local_date"],
        reminded_at=task.reminded_at,
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


def _payload_fields(payload) -> set[str]:
    if hasattr(payload, "model_fields_set"):
        return set(payload.model_fields_set)
    return set(getattr(payload, "__fields_set__", set()))


def _parse_due_at(value: str | None, user: User):
    due_at, is_date_only = parse_user_datetime(value, user.timezone)
    if value is None:
        return due_at, None
    return due_at, "date" if is_date_only else "time"


def _parse_remind_at(value: str | None, user: User):
    remind_at, is_date_only = parse_user_datetime(value, user.timezone)
    if value is not None and is_date_only:
        raise ValueError("Reminder time requires a datetime.")
    return remind_at


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


@router.post(
    "/",
    response={201: TaskOut, 400: ErrorOut, 401: ErrorOut},
)
def create_task_endpoint(request: AuthedHttpRequest, payload: TaskCreateIn):
    user = request.auth
    name = payload.name.strip()
    if not name:
        return Status(400, {"detail": "Name cannot be blank."})

    try:
        due_at, inferred_due_type = _parse_due_at(payload.due_at, user)
    except ValueError:
        return Status(400, {"detail": "Invalid due_at."})
    try:
        remind_at = _parse_remind_at(payload.remind_at, user)
    except ValueError:
        return Status(400, {"detail": "Invalid remind_at."})

    try:
        task = create_task(
            user_id=user.pk,
            name=name,
            description=payload.description,
            agent_notes=payload.agent_notes,
            status=payload.status or TaskStatus.PENDING,
            priority=payload.priority if payload.priority is not None else 0,
            due_at=due_at,
            due_type=payload.due_type or inferred_due_type or "time",
            tags=payload.tags,
            remind_at=remind_at,
        )
    except ValueError as exc:
        return Status(400, {"detail": str(exc)})
    return Status(201, _to_task_out(task, user))


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


@router.patch(
    "/{task_id}",
    response={200: TaskOut, 400: ErrorOut, 401: ErrorOut, 404: ErrorOut},
)
def update_task_endpoint(
    request: AuthedHttpRequest,
    task_id: UUID,
    payload: TaskUpdateIn,
):
    user = request.auth
    try:
        task = _base_queryset(user).get(pk=task_id)
    except Task.DoesNotExist:
        return Status(404, {"detail": "Not found."})

    fields = _payload_fields(payload)

    name = UNSET
    if "name" in fields and payload.name is not None:
        clean_name = payload.name.strip()
        if not clean_name:
            return Status(400, {"detail": "Name cannot be blank."})
        name = clean_name

    due_at = UNSET
    due_type = UNSET
    clear_due_at = bool(payload.clear_due_at)
    if clear_due_at and "due_at" in fields and payload.due_at is not None:
        return Status(
            400,
            {"detail": "Cannot set due_at and clear_due_at in the same update."},
        )
    remind_at = UNSET
    clear_remind_at = bool(payload.clear_remind_at)
    if clear_remind_at and "remind_at" in fields and payload.remind_at is not None:
        return Status(
            400,
            {"detail": "Cannot set remind_at and clear_remind_at in the same update."},
        )
    if "remind_at" in fields:
        try:
            remind_at = _parse_remind_at(payload.remind_at, user)
        except ValueError:
            return Status(400, {"detail": "Invalid remind_at."})

    if "due_at" in fields:
        try:
            due_at, inferred_due_type = _parse_due_at(payload.due_at, user)
        except ValueError:
            return Status(400, {"detail": "Invalid due_at."})
        if payload.due_at is not None:
            due_type = payload.due_type or inferred_due_type or "time"
        elif payload.due_type is not None:
            due_type = payload.due_type
    elif payload.due_type is not None:
        due_type = payload.due_type

    try:
        update_task(
            task,
            audit_actor_id=user.pk,
            name=name,
            description=payload.description if "description" in fields else UNSET,
            agent_notes=payload.agent_notes if "agent_notes" in fields else UNSET,
            status=payload.status if payload.status is not None else UNSET,
            priority=payload.priority if payload.priority is not None else UNSET,
            due_at=due_at,
            due_type=due_type,
            tags=payload.tags if payload.tags is not None else UNSET,
            clear_due_at=clear_due_at,
            remind_at=remind_at,
            clear_remind_at=clear_remind_at,
        )
    except ValueError as exc:
        return Status(400, {"detail": str(exc)})

    task.refresh_from_db()
    return Status(200, _to_task_out(task, user))


@router.delete(
    "/{task_id}",
    response={204: None, 401: ErrorOut, 404: ErrorOut},
)
def delete_task_endpoint(request: AuthedHttpRequest, task_id: UUID):
    user = request.auth
    try:
        task = _base_queryset(user).get(pk=task_id)
    except Task.DoesNotExist:
        return Status(404, {"detail": "Not found."})

    soft_delete_task(task, audit_actor_id=user.pk)
    return Status(204, None)


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
