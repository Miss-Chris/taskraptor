from datetime import datetime
from uuid import UUID

from ninja import Schema


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

