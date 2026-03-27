"""
E2E: full task lifecycle through the HTTP API.

Requires a real Postgres database — no mocks. pytest-django creates and tears
down the test database automatically. Set DJANGO_SETTINGS_MODULE in pytest.ini
(already done) so it picks up the local settings with the DB config.
"""

import json

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.tasks.models import Task


@pytest.mark.django_db
def test_full_task_lifecycle(anon_client: Client) -> None:
    # ------------------------------------------------------------------
    # 1. Create a user directly in the DB (simulates registration).
    # ------------------------------------------------------------------
    user = User.objects.create_user(email="raptor@example.com", password="hunter2!")
    assert user.pk is not None

    # ------------------------------------------------------------------
    # 2. Login via the API.
    # ------------------------------------------------------------------
    resp = anon_client.post(
        "/api/auth/login",
        data=json.dumps({"email": "raptor@example.com", "password": "hunter2!"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["email"] == "raptor@example.com"
    assert body["id"] == user.pk

    # ------------------------------------------------------------------
    # 3. Confirm /me returns the logged-in user.
    # ------------------------------------------------------------------
    resp = anon_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "raptor@example.com"

    # ------------------------------------------------------------------
    # 4. Create a task.
    # ------------------------------------------------------------------
    resp = anon_client.post(
        "/api/tasks/",
        data=json.dumps({"description": "Buy oat milk"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    task_data = resp.json()
    task_id: int = task_data["id"]
    assert task_data["description"] == "Buy oat milk"
    assert task_data["status"] == "pending"
    assert task_data["due_at"] is None

    # ------------------------------------------------------------------
    # 5. List tasks — should contain our new task.
    # ------------------------------------------------------------------
    resp = anon_client.get("/api/tasks/")
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert task_id in ids

    # ------------------------------------------------------------------
    # 6. Mark the task done.
    # ------------------------------------------------------------------
    resp = anon_client.patch(
        f"/api/tasks/{task_id}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "done"

    # ------------------------------------------------------------------
    # 7. Assert DB state — the source of truth.
    # ------------------------------------------------------------------
    task = Task.objects.get(pk=task_id)
    assert task.status == Task.Status.DONE
    assert task.user_id == user.pk
    assert task.description == "Buy oat milk"

    # ------------------------------------------------------------------
    # 8. Delete the task.
    # ------------------------------------------------------------------
    resp = anon_client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert not Task.objects.filter(pk=task_id).exists()

    # ------------------------------------------------------------------
    # 9. Logout.
    # ------------------------------------------------------------------
    resp = anon_client.post("/api/auth/logout")
    assert resp.status_code == 200

    # After logout, /me should return 401.
    resp = anon_client.get("/api/auth/me")
    assert resp.status_code == 401
