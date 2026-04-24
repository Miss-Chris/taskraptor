from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client
from django.utils import timezone

from tasks.models import TaskStatus
from tasks.services import create_task

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
    assert "done" not in by_tag
    assert "cancelled" not in by_tag
    assert "archived" not in by_tag
    assert "deleted" not in by_tag
    assert "other" not in by_tag
