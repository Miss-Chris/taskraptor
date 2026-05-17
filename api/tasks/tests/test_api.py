from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client
from django.utils import timezone

from tasks.models import AuditAction, Task, TaskAuditLog, TaskStatus
from tasks.services import create_task, update_task

REGISTER_URL = "/api/auth/register"
LIST_URL = "/api/tasks/"
FACETS_URL = "/api/tasks/facets"


@pytest.fixture
def client():
    return Client()


def _register_and_token(client, email: str) -> str:
    reg = client.post(
        REGISTER_URL,
        data={"email": email, "password": "secret123"},
        content_type="application/json",
    )
    assert reg.status_code == 201
    return reg.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.mark.django_db
def test_list_tasks_unauthenticated(client):
    assert client.get(LIST_URL).status_code == 401


@pytest.mark.django_db
def test_facets_unauthenticated(client):
    assert client.get(FACETS_URL).status_code == 401


@pytest.mark.django_db
def test_get_task_unauthenticated(client):
    from uuid import uuid4

    assert client.get(f"/api/tasks/{uuid4()}").status_code == 401


@pytest.mark.django_db
def test_get_task_audit_logs_unauthenticated(client):
    from uuid import uuid4

    assert client.get(f"/api/tasks/{uuid4()}/audit-logs").status_code == 401


@pytest.mark.django_db
def test_create_task_unauthenticated(client):
    assert (
        client.post(
            LIST_URL,
            data={"name": "Nope"},
            content_type="application/json",
        ).status_code
        == 401
    )


@pytest.mark.django_db
def test_update_task_unauthenticated(client):
    from uuid import uuid4

    assert (
        client.patch(
            f"/api/tasks/{uuid4()}",
            data={"name": "Nope"},
            content_type="application/json",
        ).status_code
        == 401
    )


@pytest.mark.django_db
def test_delete_task_unauthenticated(client):
    from uuid import uuid4

    assert client.delete(f"/api/tasks/{uuid4()}").status_code == 401


@pytest.mark.django_db
def test_create_task_success_with_due_date_normalization(client):
    from accounts.models import User

    token = _register_and_token(client, "create-task@example.com")
    user = User.objects.get(email="create-task@example.com")
    user.timezone = "America/Toronto"
    user.save(update_fields=["timezone"])

    response = client.post(
        LIST_URL,
        data={
            "name": "  File taxes  ",
            "description": "Annual filing",
            "agent_notes": "Ask for receipts",
            "priority": 3,
            "due_at": "2026-04-10",
            "tags": ["personal"],
        },
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "File taxes"
    assert body["description"] == "Annual filing"
    assert body["agent_notes"] == "Ask for receipts"
    assert body["status"] == TaskStatus.PENDING
    assert body["priority"] == 3
    assert body["due_type"] == "date"
    assert body["due_date_local"] == "2026-04-10"
    assert body["tags"] == ["personal"]

    task = Task.objects.get(pk=body["id"])
    assert task.user == user
    assert task.due_at is not None


@pytest.mark.django_db
def test_create_task_rejects_blank_name(client):
    token = _register_and_token(client, "blank-create@example.com")

    response = client.post(
        LIST_URL,
        data={"name": "   "},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Name cannot be blank."


@pytest.mark.django_db
def test_create_task_rejects_invalid_due_at(client):
    token = _register_and_token(client, "bad-due-create@example.com")

    response = client.post(
        LIST_URL,
        data={"name": "Bad date", "due_at": "not-a-date"},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid due_at."


@pytest.mark.django_db
def test_create_task_accepts_future_reminder_and_serializes_local_fields(client, monkeypatch):
    from accounts.models import User

    token = _register_and_token(client, "create-reminder@example.com")
    user = User.objects.get(email="create-reminder@example.com")
    user.timezone = "America/Toronto"
    user.save(update_fields=["timezone"])
    monkeypatch.setattr("tasks.services.timezone.now", lambda: datetime(2026, 4, 10, 12, 0, tzinfo=UTC))

    response = client.post(
        LIST_URL,
        data={"name": "Call mom", "remind_at": "2026-04-10T09:30:00"},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["remind_at"] == "2026-04-10T13:30:00Z"
    assert body["remind_at_local"] == "2026-04-10T09:30:00-04:00"
    assert body["remind_date_local"] == "2026-04-10"
    assert body["reminded_at"] is None


@pytest.mark.django_db
def test_create_task_rejects_invalid_and_past_reminder(client, monkeypatch):
    token = _register_and_token(client, "bad-reminder@example.com")
    monkeypatch.setattr("tasks.services.timezone.now", lambda: datetime(2026, 4, 10, 12, 0, tzinfo=UTC))

    invalid = client.post(
        LIST_URL,
        data={"name": "Bad", "remind_at": "2026-04-10"},
        content_type="application/json",
        **_auth(token),
    )
    past = client.post(
        LIST_URL,
        data={"name": "Past", "remind_at": "2026-04-10T07:00:00Z"},
        content_type="application/json",
        **_auth(token),
    )

    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "Invalid remind_at."
    assert past.status_code == 400
    assert past.json()["detail"] == "Reminder time must be in the future."


@pytest.mark.django_db
def test_update_task_success_audits_changes_and_sets_completed_at(client):
    from accounts.models import User

    token = _register_and_token(client, "update-task@example.com")
    user = User.objects.get(email="update-task@example.com")
    task = create_task(user_id=user.pk, name="Initial", tags=["work"], priority=1)

    response = client.patch(
        f"/api/tasks/{task.pk}",
        data={
            "name": "  Renamed  ",
            "description": "Customer-facing detail",
            "agent_notes": "Internal follow-up",
            "status": TaskStatus.COMPLETED,
            "priority": 5,
            "tags": ["done"],
        },
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["description"] == "Customer-facing detail"
    assert body["agent_notes"] == "Internal follow-up"
    assert body["status"] == TaskStatus.COMPLETED
    assert body["priority"] == 5
    assert body["tags"] == ["done"]
    assert body["completed_at"] is not None

    actions = set(
        TaskAuditLog.objects.filter(task=task).values_list("action", flat=True)
    )
    assert actions == {
        AuditAction.NAME_CHANGED,
        AuditAction.DESCRIPTION_CHANGED,
        AuditAction.AGENT_NOTES_CHANGED,
        AuditAction.STATUS_CHANGED,
        AuditAction.PRIORITY_CHANGED,
        AuditAction.TAGS_CHANGED,
    }


@pytest.mark.django_db
def test_update_task_can_clear_due_at(client):
    from accounts.models import User

    token = _register_and_token(client, "clear-due@example.com")
    user = User.objects.get(email="clear-due@example.com")
    task = create_task(
        user_id=user.pk,
        name="Has due date",
        due_at=datetime(2026, 4, 10, 13, 30, tzinfo=UTC),
    )

    response = client.patch(
        f"/api/tasks/{task.pk}",
        data={"clear_due_at": True},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["due_at"] is None
    task.refresh_from_db()
    assert task.due_at is None


@pytest.mark.django_db
def test_update_task_sets_and_clears_reminder_with_audit(client, monkeypatch):
    from accounts.models import User

    token = _register_and_token(client, "update-reminder@example.com")
    user = User.objects.get(email="update-reminder@example.com")
    task = create_task(user_id=user.pk, name="Follow up")
    monkeypatch.setattr("tasks.services.timezone.now", lambda: datetime(2026, 4, 10, 12, 0, tzinfo=UTC))

    set_response = client.patch(
        f"/api/tasks/{task.pk}",
        data={"remind_at": "2026-04-10T13:00:00Z"},
        content_type="application/json",
        **_auth(token),
    )
    clear_response = client.patch(
        f"/api/tasks/{task.pk}",
        data={"clear_remind_at": True},
        content_type="application/json",
        **_auth(token),
    )

    assert set_response.status_code == 200
    assert set_response.json()["remind_at"] == "2026-04-10T13:00:00Z"
    assert clear_response.status_code == 200
    assert clear_response.json()["remind_at"] is None
    assert TaskAuditLog.objects.filter(task=task, action=AuditAction.REMINDER_CHANGED).count() == 2


@pytest.mark.django_db
def test_update_task_rejects_due_at_with_clear_due_at(client):
    from accounts.models import User

    token = _register_and_token(client, "bad-clear-due@example.com")
    user = User.objects.get(email="bad-clear-due@example.com")
    task = create_task(user_id=user.pk, name="Has due date")

    response = client.patch(
        f"/api/tasks/{task.pk}",
        data={"due_at": "2026-04-10T10:00:00", "clear_due_at": True},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Cannot set due_at and clear_due_at in the same update."
    )


@pytest.mark.django_db
def test_update_task_404_for_other_user(client):
    from accounts.models import User

    token = _register_and_token(client, "update-a@example.com")
    other = User.objects.create_user("update-b@example.com", "secret123")
    task = create_task(user_id=other.pk, name="Secret")

    response = client.patch(
        f"/api/tasks/{task.pk}",
        data={"name": "Stolen"},
        content_type="application/json",
        **_auth(token),
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_delete_task_soft_deletes_and_audits(client):
    from accounts.models import User

    token = _register_and_token(client, "delete-task@example.com")
    user = User.objects.get(email="delete-task@example.com")
    task = create_task(user_id=user.pk, name="Delete me")

    response = client.delete(f"/api/tasks/{task.pk}", **_auth(token))

    assert response.status_code == 204
    task.refresh_from_db()
    assert task.deleted_at is not None
    assert TaskAuditLog.objects.filter(
        task=task,
        action=AuditAction.DELETED,
        actor_id=user.pk,
    ).exists()

    list_response = client.get(LIST_URL, **_auth(token))
    assert list_response.status_code == 200
    assert list_response.json()["tasks"] == []


@pytest.mark.django_db
def test_delete_task_404_for_other_user(client):
    from accounts.models import User

    token = _register_and_token(client, "delete-a@example.com")
    other = User.objects.create_user("delete-b@example.com", "secret123")
    task = create_task(user_id=other.pk, name="Secret")

    response = client.delete(f"/api/tasks/{task.pk}", **_auth(token))

    assert response.status_code == 404
    task.refresh_from_db()
    assert task.deleted_at is None


@pytest.mark.django_db
def test_list_tasks_only_non_deleted_scoped_to_user(client):
    token = _register_and_token(client, "u1@example.com")
    from accounts.models import User

    u1 = User.objects.get(email="u1@example.com")
    u2 = User.objects.create_user("u2@example.com", "secret123")

    t1 = create_task(user_id=u1.pk, name="Mine")
    create_task(user_id=u2.pk, name="Yours")
    t1.deleted_at = timezone.now()
    t1.save(update_fields=["deleted_at"])

    r = client.get(LIST_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0
    assert data["tasks"] == []


@pytest.mark.django_db
def test_list_tasks_filter_by_status_and_tag_and_priority(client):
    token = _register_and_token(client, "f1@example.com")
    from accounts.models import User

    u1 = User.objects.get(email="f1@example.com")
    create_task(
        user_id=u1.pk,
        name="A",
        status=TaskStatus.PENDING,
        tags=["work"],
        priority=1,
    )
    create_task(
        user_id=u1.pk,
        name="B",
        status=TaskStatus.IN_PROGRESS,
        tags=["personal"],
        priority=5,
    )

    r = client.get(
        f"{LIST_URL}?status={TaskStatus.PENDING}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r.json()["count"] == 1
    assert r.json()["tasks"][0]["name"] == "A"

    r2 = client.get(
        f"{LIST_URL}?tag=personal",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r2.json()["count"] == 1
    assert r2.json()["tasks"][0]["name"] == "B"

    r3 = client.get(
        f"{LIST_URL}?priority=5",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r3.json()["count"] == 1
    assert r3.json()["tasks"][0]["name"] == "B"

    r4 = client.get(
        f"{LIST_URL}?min_priority=1&max_priority=3",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r4.json()["count"] == 1
    assert r4.json()["tasks"][0]["name"] == "A"


@pytest.mark.django_db
def test_list_tasks_upcoming_excludes_past_and_completed(client):
    token = _register_and_token(client, "f2@example.com")
    from accounts.models import User

    u1 = User.objects.get(email="f2@example.com")
    now = timezone.now()
    create_task(
        user_id=u1.pk,
        name="Future",
        due_at=now + timedelta(days=1),
        status=TaskStatus.PENDING,
    )
    create_task(
        user_id=u1.pk,
        name="Past",
        due_at=now - timedelta(days=1),
        status=TaskStatus.PENDING,
    )
    create_task(
        user_id=u1.pk,
        name="Done but future",
        due_at=now + timedelta(days=1),
        status=TaskStatus.COMPLETED,
    )

    r = client.get(
        f"{LIST_URL}?upcoming=True",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tasks"]}
    assert names == {"Future"}


@pytest.mark.django_db
def test_list_tasks_returns_local_due_at_fields(client):
    token = _register_and_token(client, "local-api@example.com")
    from accounts.models import User

    user = User.objects.get(email="local-api@example.com")
    user.timezone = "America/Toronto"
    user.save(update_fields=["timezone"])
    create_task(
        user_id=user.pk,
        name="Local API",
        due_at=datetime(2026, 4, 10, 13, 30, tzinfo=UTC),
    )

    response = client.get(LIST_URL, HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 200
    task = response.json()["tasks"][0]
    assert task["due_at_local"] == "2026-04-10T09:30:00-04:00"
    assert task["due_date_local"] == "2026-04-10"
    assert task["timezone"] == "America/Toronto"


@pytest.mark.django_db
def test_get_task_404_for_other_user(client):
    from accounts.models import User

    token = _register_and_token(client, "a@example.com")
    other = User.objects.create_user("b@example.com", "secret123")
    t = create_task(user_id=other.pk, name="Secret")

    r = client.get(
        f"/api/tasks/{t.pk}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r.status_code == 404


@pytest.mark.django_db
def test_get_task_success(client):
    from accounts.models import User

    token = _register_and_token(client, "c@example.com")
    u = User.objects.get(email="c@example.com")
    t = create_task(user_id=u.pk, name="X", tags=["work"])

    r = client.get(
        f"/api/tasks/{t.pk}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "X"
    assert body["tags"] == ["work"]


@pytest.mark.django_db
def test_get_task_audit_logs_404_for_other_user(client):
    from accounts.models import User

    token = _register_and_token(client, "audit-a@example.com")
    other = User.objects.create_user("audit-b@example.com", "secret123")
    task = create_task(user_id=other.pk, name="Secret")
    update_task(task, name="Still secret", audit_actor_id=other.pk)

    response = client.get(
        f"/api/tasks/{task.pk}/audit-logs",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_task_audit_logs_success_ordered_newest_first(client):
    from accounts.models import User

    token = _register_and_token(client, "audit-c@example.com")
    user = User.objects.get(email="audit-c@example.com")
    task = create_task(user_id=user.pk, name="Initial", tags=["work"], priority=1)

    update_task(task, name="Renamed", audit_actor_id=user.pk)
    update_task(task, priority=3, audit_actor_id=user.pk)
    other_task = create_task(user_id=user.pk, name="Other")
    update_task(other_task, name="Other renamed", audit_actor_id=user.pk)

    response = client.get(
        f"/api/tasks/{task.pk}/audit-logs",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 200
    logs = response.json()["audit_logs"]
    assert [log["action"] for log in logs] == ["priority_changed", "name_changed"]
    assert logs[0]["task_id"] == str(task.pk)
    assert logs[0]["old_value"] == 1
    assert logs[0]["new_value"] == 3
    assert logs[0]["actor_id"] == str(user.pk)


@pytest.mark.django_db
def test_get_task_and_list_include_description_and_agent_notes(client):
    from accounts.models import User

    token = _register_and_token(client, "task-fields@example.com")
    user = User.objects.get(email="task-fields@example.com")
    task = create_task(
        user_id=user.pk,
        name="Detailed task",
        description="Visible context",
        agent_notes="Internal context",
    )

    detail = client.get(f"/api/tasks/{task.pk}", **_auth(token))
    listing = client.get(LIST_URL, **_auth(token))

    assert detail.status_code == 200
    assert detail.json()["description"] == "Visible context"
    assert detail.json()["agent_notes"] == "Internal context"
    assert listing.status_code == 200
    assert listing.json()["tasks"][0]["description"] == "Visible context"
    assert listing.json()["tasks"][0]["agent_notes"] == "Internal context"


@pytest.mark.django_db
def test_get_task_audit_logs_empty(client):
    from accounts.models import User

    token = _register_and_token(client, "audit-d@example.com")
    user = User.objects.get(email="audit-d@example.com")
    task = create_task(user_id=user.pk, name="No changes")

    response = client.get(
        f"/api/tasks/{task.pk}/audit-logs",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 200
    assert response.json() == {"audit_logs": []}


@pytest.mark.django_db
def test_facets_include_default_tags_for_new_user(client):
    token = _register_and_token(client, "default-facets@example.com")

    r = client.get(FACETS_URL, HTTP_AUTHORIZATION=f"Bearer {token}")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["tag_counts"] == [
        {"tag": "work", "count": 0},
        {"tag": "personal", "count": 0},
        {"tag": "family", "count": 0},
    ]


@pytest.mark.django_db
def test_facets_status_and_tags(client):
    from accounts.models import User

    token = _register_and_token(client, "d@example.com")
    u = User.objects.get(email="d@example.com")
    other = User.objects.create_user("facets-other@example.com", "secret123")
    create_task(
        user_id=u.pk,
        name="T1",
        status=TaskStatus.PENDING,
        tags=["work", "a"],
    )
    create_task(
        user_id=u.pk,
        name="T2",
        status=TaskStatus.PENDING,
        tags=["work"],
    )
    create_task(
        user_id=u.pk,
        name="Completed",
        status=TaskStatus.COMPLETED,
        tags=["work", "done"],
    )
    create_task(
        user_id=u.pk,
        name="Cancelled",
        status=TaskStatus.CANCELLED,
        tags=["cancelled"],
    )
    archived = create_task(
        user_id=u.pk,
        name="Archived",
        status=TaskStatus.PENDING,
        tags=["archived"],
    )
    archived.archived_at = timezone.now()
    archived.save(update_fields=["archived_at"])
    deleted = create_task(
        user_id=u.pk,
        name="Deleted",
        status=TaskStatus.PENDING,
        tags=["deleted"],
    )
    deleted.deleted_at = timezone.now()
    deleted.save(update_fields=["deleted_at"])
    create_task(user_id=other.pk, name="Other", tags=["other"])

    r = client.get(FACETS_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    by_status = {s["status"]: s["count"] for s in data["status_counts"]}
    assert by_status[TaskStatus.PENDING] == 3
    assert by_status[TaskStatus.COMPLETED] == 1
    assert by_status[TaskStatus.CANCELLED] == 1
    by_tag = {t["tag"]: t["count"] for t in data["tag_counts"]}
    assert by_tag["work"] == 2
    assert by_tag["a"] == 1
    assert by_tag["personal"] == 0
    assert by_tag["family"] == 0
    assert "done" not in by_tag
    assert "cancelled" not in by_tag
    assert "archived" not in by_tag
    assert "deleted" not in by_tag
    assert "other" not in by_tag
