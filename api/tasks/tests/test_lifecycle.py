from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from agent.tools import execute_tool
from tasks.models import AuditAction, TaskAuditLog, TaskStatus
from tasks.services import create_task, update_task

User = get_user_model()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email="task_lifecycle@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
def test_update_task_sets_and_clears_completed_at(test_user):
    task = create_task(user_id=test_user.pk, name="Buy milk")

    update_task(task, status=TaskStatus.COMPLETED, audit_actor_id=test_user.pk)
    task.refresh_from_db()
    assert task.completed_at is not None

    update_task(task, status=TaskStatus.PENDING, audit_actor_id=test_user.pk)
    task.refresh_from_db()
    assert task.completed_at is None


@pytest.mark.django_db
def test_edit_task_tool_can_clear_due_at(test_user):
    task = create_task(
        user_id=test_user.pk,
        name="Pay rent",
        due_at=timezone.now() + timedelta(days=1),
    )

    result = json.loads(
        execute_tool(
            "edit_task",
            {"task_id": task.pk, "clear_due_at": True},
            test_user.pk,
        )
    )

    assert result["ok"] is True
    assert "due_at" in result["updated_fields"]
    task.refresh_from_db()
    assert task.due_at is None


@pytest.mark.django_db
def test_delete_task_tool_soft_deletes_and_audits(test_user):
    task = create_task(user_id=test_user.pk, name="Archive docs")

    result = json.loads(execute_tool("delete_task", {"task_id": task.pk}, test_user.pk))

    assert result["ok"] is True
    task.refresh_from_db()
    assert task.deleted_at is not None

    log = TaskAuditLog.objects.get(task=task, action=AuditAction.DELETED)
    assert log.actor_id == test_user.pk
    assert log.new_value["deleted_at"] is not None
