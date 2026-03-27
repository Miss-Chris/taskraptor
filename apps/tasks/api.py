from datetime import datetime
from typing import Optional

from django.http import HttpRequest
from ninja import Router, Schema
from ninja.security import django_auth

from .models import Task

router = Router()


class TaskIn(Schema):
    description: str
    due_at: Optional[datetime] = None


class TaskPatch(Schema):
    description: Optional[str] = None
    status: Optional[str] = None
    due_at: Optional[datetime] = None


class TaskOut(Schema):
    id: int
    description: str
    status: str
    created_at: datetime
    due_at: Optional[datetime]


@router.get("/", auth=django_auth, response=list[TaskOut])
def list_tasks(request: HttpRequest):
    return Task.objects.filter(user=request.user)


@router.post("/", auth=django_auth, response=TaskOut)
def create_task(request: HttpRequest, data: TaskIn):
    return Task.objects.create(user=request.user, **data.dict())


@router.get("/{task_id}", auth=django_auth, response={200: TaskOut, 404: dict})
def get_task(request: HttpRequest, task_id: int):
    try:
        return 200, Task.objects.get(id=task_id, user=request.user)
    except Task.DoesNotExist:
        return 404, {"detail": "Not found"}


@router.patch("/{task_id}", auth=django_auth, response={200: TaskOut, 404: dict})
def update_task(request: HttpRequest, task_id: int, data: TaskPatch):
    try:
        task = Task.objects.get(id=task_id, user=request.user)
    except Task.DoesNotExist:
        return 404, {"detail": "Not found"}
    for field, value in data.dict(exclude_unset=True).items():
        setattr(task, field, value)
    task.save()
    return 200, task


@router.delete("/{task_id}", auth=django_auth, response={200: dict, 404: dict})
def delete_task(request: HttpRequest, task_id: int):
    try:
        task = Task.objects.get(id=task_id, user=request.user)
    except Task.DoesNotExist:
        return 404, {"detail": "Not found"}
    task.delete()
    return 200, {"ok": True}
