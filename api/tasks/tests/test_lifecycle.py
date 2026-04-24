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


@pytest.mark.django_db
def test_query_tasks_tool_only_returns_current_users_active_tasks(test_user):
    other_user = User.objects.create_user(
        email="other_task_lifecycle@example.com",
        password="testpass123",
    )
    visible = create_task(user_id=test_user.pk, name="Visible task")
    deleted = create_task(user_id=test_user.pk, name="Deleted task")
    deleted.deleted_at = timezone.now()
    deleted.save(update_fields=["deleted_at"])
    create_task(user_id=other_user.pk, name="Other user's task")

    result = json.loads(execute_tool("query_tasks", {}, test_user.pk))

    assert result["ok"] is True
    assert result["count"] == 1
    assert result["tasks"][0]["id"] == str(visible.pk)
    assert result["tasks"][0]["name"] == "Visible task"


@pytest.mark.django_db
def test_query_tasks_tool_filters_by_status_tag_priority_upcoming_and_search(test_user):
    now = timezone.now()
    create_task(
        user_id=test_user.pk,
        name="Pay invoice",
        status=TaskStatus.PENDING,
        priority=5,
        due_at=now + timedelta(days=1),
        tags=["finance", "urgent"],
    )
    create_task(
        user_id=test_user.pk,
        name="Read article",
        status=TaskStatus.COMPLETED,
        priority=1,
        due_at=now + timedelta(days=2),
        tags=["reading"],
    )
    create_task(
        user_id=test_user.pk,
        name="Past finance task",
        status=TaskStatus.PENDING,
        priority=3,
        due_at=now - timedelta(days=1),
        tags=["finance"],
    )

    result = json.loads(
        execute_tool(
            "query_tasks",
            {
                "status": "pending",
                "tag": "finance",
                "upcoming": True,
                "min_priority": 4,
                "max_priority": 5,
                "search": "invoice",
            },
            test_user.pk,
        )
    )

    assert result["ok"] is True
    assert result["count"] == 1
    assert result["tasks"][0]["name"] == "Pay invoice"


@pytest.mark.django_db
def test_query_tasks_tool_can_exclude_completed_tasks(test_user):
    create_task(user_id=test_user.pk, name="Open task", status=TaskStatus.PENDING)
    create_task(user_id=test_user.pk, name="Done task", status=TaskStatus.COMPLETED)

    result = json.loads(
        execute_tool("query_tasks", {"include_completed": False}, test_user.pk)
    )

    assert result["ok"] is True
    assert [task["name"] for task in result["tasks"]] == ["Open task"]


@pytest.mark.django_db
def test_query_tasks_tool_caps_limit_at_100(test_user):
    for index in range(105):
        create_task(user_id=test_user.pk, name=f"Task {index:03d}")

    result = json.loads(execute_tool("query_tasks", {"limit": 500}, test_user.pk))

    assert result["ok"] is True
    assert result["count"] == 100
    assert len(result["tasks"]) == 100


@pytest.mark.django_db
def test_run_sql_tool_is_not_exposed(test_user):
    result = json.loads(
        execute_tool(
            "run_sql",
            {"query": "SELECT id, name FROM tasks_task"},
            test_user.pk,
        )
    )

    assert result == {"ok": False, "error": "Unknown tool: run_sql"}
