from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from agent.tools import execute_tool
from tasks.models import AuditAction, DueType, Task, TaskAuditLog, TaskStatus
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
def test_task_service_normalizes_naive_due_at_in_user_timezone(test_user):
    test_user.timezone = "America/Toronto"
    test_user.save(update_fields=["timezone"])

    task = create_task(
        user_id=test_user.pk,
        name="Service local",
        due_at=datetime(2026, 4, 10, 9, 30),
    )

    assert task.due_at == datetime(2026, 4, 10, 13, 30, tzinfo=UTC)


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
def test_set_and_clear_task_reminder_tools(test_user, monkeypatch):
    task = create_task(user_id=test_user.pk, name="Call dentist")
    monkeypatch.setattr("tasks.services.timezone.now", lambda: datetime(2026, 4, 10, 12, 0, tzinfo=UTC))

    set_result = json.loads(
        execute_tool(
            "set_task_reminder",
            {"task_id": task.pk, "remind_at": "2026-04-10T13:00:00Z"},
            test_user.pk,
        )
    )
    clear_result = json.loads(
        execute_tool("clear_task_reminder", {"task_id": task.pk}, test_user.pk)
    )

    assert set_result["ok"] is True
    assert "remind_at" in set_result["updated_fields"]
    assert clear_result["ok"] is True
    task.refresh_from_db()
    assert task.remind_at is None


@pytest.mark.django_db
def test_set_task_reminder_tool_rejects_past_and_other_users_tasks(test_user, monkeypatch):
    other_user = User.objects.create_user("other-reminder@example.com", "testpass123")
    task = create_task(user_id=other_user.pk, name="Private")
    monkeypatch.setattr("tasks.services.timezone.now", lambda: datetime(2026, 4, 10, 12, 0, tzinfo=UTC))

    missing = json.loads(
        execute_tool(
            "set_task_reminder",
            {"task_id": task.pk, "remind_at": "2026-04-10T13:00:00Z"},
            test_user.pk,
        )
    )
    own = create_task(user_id=test_user.pk, name="Own")
    past = json.loads(
        execute_tool(
            "set_task_reminder",
            {"task_id": own.pk, "remind_at": "2026-04-10T11:00:00Z"},
            test_user.pk,
        )
    )

    assert missing["ok"] is False
    assert past["ok"] is False
    assert past["error"] == "Reminder time must be in the future."


@pytest.mark.django_db
def test_create_task_tool_interprets_naive_due_at_in_user_timezone(test_user):
    test_user.timezone = "America/Toronto"
    test_user.save(update_fields=["timezone"])

    result = json.loads(
        execute_tool(
            "create_task",
            {"name": "Local meeting", "due_at": "2026-04-10T09:30:00"},
            test_user.pk,
        )
    )

    assert result["ok"] is True
    task = Task.objects.get(pk=result["task_id"])
    assert task.due_at == datetime(2026, 4, 10, 13, 30, tzinfo=UTC)
    assert task.due_type == DueType.TIME


@pytest.mark.django_db
def test_create_task_tool_normalizes_aware_due_at_to_utc(test_user):
    result = json.loads(
        execute_tool(
            "create_task",
            {"name": "Offset meeting", "due_at": "2026-04-10T09:30:00-07:00"},
            test_user.pk,
        )
    )

    assert result["ok"] is True
    task = Task.objects.get(pk=result["task_id"])
    assert task.due_at == datetime(2026, 4, 10, 16, 30, tzinfo=UTC)


@pytest.mark.django_db
def test_create_task_tool_treats_date_only_due_at_as_local_day_end(test_user):
    test_user.timezone = "America/Toronto"
    test_user.save(update_fields=["timezone"])

    result = json.loads(
        execute_tool(
            "create_task",
            {"name": "File taxes", "due_at": "2026-04-10"},
            test_user.pk,
        )
    )

    assert result["ok"] is True
    task = Task.objects.get(pk=result["task_id"])
    assert task.due_at == datetime(2026, 4, 11, 3, 59, 59, 999999, tzinfo=UTC)
    assert task.due_type == DueType.DATE


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
def test_query_tasks_tool_returns_utc_and_local_due_at_fields(test_user):
    test_user.timezone = "America/Toronto"
    test_user.save(update_fields=["timezone"])
    task = create_task(
        user_id=test_user.pk,
        name="Local fields",
        due_at=datetime(2026, 4, 10, 13, 30, tzinfo=UTC),
    )

    result = json.loads(execute_tool("query_tasks", {"search": "Local fields"}, test_user.pk))

    assert result["ok"] is True
    returned = result["tasks"][0]
    assert returned["id"] == str(task.pk)
    assert returned["due_at"] == "2026-04-10T13:30:00+00:00"
    assert returned["due_at_local"] == "2026-04-10T09:30:00-04:00"
    assert returned["due_date_local"] == "2026-04-10"
    assert returned["timezone"] == "America/Toronto"


@pytest.mark.django_db
def test_query_tasks_tool_returns_reminder_fields(test_user):
    test_user.timezone = "America/Toronto"
    test_user.save(update_fields=["timezone"])
    task = create_task(user_id=test_user.pk, name="Reminder fields")
    task.remind_at = datetime(2026, 4, 10, 13, 30, tzinfo=UTC)
    task.reminded_at = datetime(2026, 4, 10, 13, 31, tzinfo=UTC)
    task.save(update_fields=["remind_at", "reminded_at"])

    result = json.loads(execute_tool("query_tasks", {"search": "Reminder fields"}, test_user.pk))
    returned = result["tasks"][0]

    assert returned["remind_at"] == "2026-04-10T13:30:00+00:00"
    assert returned["remind_at_local"] == "2026-04-10T09:30:00-04:00"
    assert returned["remind_date_local"] == "2026-04-10"
    assert returned["reminded_at"] == "2026-04-10T13:31:00+00:00"


@pytest.mark.django_db
def test_same_local_due_at_stores_different_utc_instants_by_user_timezone(test_user):
    other_user = User.objects.create_user(
        email="pacific_task_lifecycle@example.com",
        password="testpass123",
        timezone="America/Los_Angeles",
    )
    test_user.timezone = "America/Toronto"
    test_user.save(update_fields=["timezone"])

    east = json.loads(
        execute_tool(
            "create_task",
            {"name": "Same local", "due_at": "2026-04-10T09:00:00"},
            test_user.pk,
        )
    )
    west = json.loads(
        execute_tool(
            "create_task",
            {"name": "Same local", "due_at": "2026-04-10T09:00:00"},
            other_user.pk,
        )
    )

    east_task = Task.objects.get(pk=east["task_id"])
    west_task = Task.objects.get(pk=west["task_id"])
    assert east_task.due_at == datetime(2026, 4, 10, 13, 0, tzinfo=UTC)
    assert west_task.due_at == datetime(2026, 4, 10, 16, 0, tzinfo=UTC)


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
