from datetime import datetime, time
from uuid import UUID

from ninja import Schema


class AutomationOut(Schema):
    id: UUID
    prompt: str
    schedule_time: time
    is_active: bool
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AutomationListOut(Schema):
    automations: list[AutomationOut]
    count: int


class AutomationCreateIn(Schema):
    prompt: str
    schedule_time: time


class AutomationUpdateIn(Schema):
    prompt: str | None = None
    schedule_time: time | None = None
    is_active: bool | None = None
