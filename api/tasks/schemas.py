from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from ninja import Schema
from pydantic import Field

TaskStatusValue = Literal["pending", "in_progress", "completed", "cancelled"]
DueTypeValue = Literal["date", "time"]


class TaskOut(Schema):
    id: UUID
    name: str
    status: str
    priority: int
    due_at: datetime | None
    due_at_local: str | None
    due_date_local: str | None
    due_type: str
    timezone: str
    tags: list[str]
    remind_at: datetime | None
    completed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime


class TaskListOut(Schema):
    tasks: list[TaskOut]
    count: int


class TaskCreateIn(Schema):
    name: str
    status: TaskStatusValue | None = None
    priority: int | None = None
    due_at: str | None = None
    due_type: DueTypeValue | None = None
    tags: list[str] = Field(default_factory=list)


class TaskUpdateIn(Schema):
    name: str | None = None
    status: TaskStatusValue | None = None
    priority: int | None = None
    due_at: str | None = None
    due_type: DueTypeValue | None = None
    clear_due_at: bool | None = None
    tags: list[str] | None = None


class StatusCountItem(Schema):
    status: str
    count: int


class TagCountItem(Schema):
    tag: str
    count: int


class TaskFacetsOut(Schema):
    status_counts: list[StatusCountItem]
    tag_counts: list[TagCountItem]
    # Total non-deleted tasks for the current user
    total: int


class TaskAuditLogOut(Schema):
    id: UUID
    task_id: UUID
    created_at: datetime
    action: str
    old_value: Any
    new_value: Any
    actor_id: UUID | None


class TaskAuditLogListOut(Schema):
    audit_logs: list[TaskAuditLogOut]
