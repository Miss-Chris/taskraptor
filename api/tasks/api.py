from __future__ import annotations

from collections import Counter
from uuid import UUID

from django.db import connection
from django.db.models import Count, QuerySet
from django.utils import timezone
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.http import AuthedHttpRequest
from accounts.schemas import ErrorOut
from accounts.models import User
from tasks.models import Task, TaskStatus
from tasks.schemas import (
    StatusCountItem,
    TagCountItem,
    TaskFacetsOut,
    TaskListOut,
    TaskOut,
)

router = Router(tags=["tasks"], auth=AuthBearer())


def _base_queryset(user: User) -> QuerySet[Task]:
    return Task.objects.filter(
        user=user,
        deleted_at__isnull=True,
    )


def _to_task_out(task: Task) -> TaskOut:
    tags = task.tags if isinstance(task.tags, list) else []
    return TaskOut(
        id=task.id,
        name=task.name,
        status=task.status,
        priority=task.priority,
        due_at=task.due_at,
        due_type=task.due_type,
        tags=[str(t) for t in tags],
        remind_at=task.remind_at,
        completed_at=task.completed_at,
        archived_at=task.archived_at,
        created_at=task.created_at,
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

    # Aggregate tag frequencies in Python; tags are JSON list of strings
    tag_counter: Counter[str] = Counter()
    for tags in base.values_list("tags", flat=True):
        if isinstance(tags, list):
            for t in tags:
                tag_counter[str(t)] += 1
    tag_counts = [
        TagCountItem(tag=tag, count=n)
        for tag, n in sorted(tag_counter.items(), key=lambda x: (-x[1], x[0]))
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
            tasks=[_to_task_out(t) for t in tasks],
            count=len(tasks),
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
    return Status(200, _to_task_out(task))
