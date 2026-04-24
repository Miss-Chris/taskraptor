from __future__ import annotations

import datetime
from uuid import uuid4

import pytest
from django.test import Client

from accounts.models import User
from automations.models import Automation

AUTOMATIONS_URL = "/api/automations/"
REGISTER_URL = "/api/auth/register"


@pytest.fixture
def client():
    return Client()


def _register_and_token(client: Client, email: str) -> str:
    response = client.post(
        REGISTER_URL,
        data={"email": email, "password": "secret123"},
        content_type="application/json",
    )
    assert response.status_code == 201
    return response.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.mark.django_db
def test_automation_api_requires_authentication(client):
    assert client.get(AUTOMATIONS_URL).status_code == 401
    assert (
        client.post(
            AUTOMATIONS_URL,
            data={"prompt": "Summarize", "schedule_time": "09:30:00"},
            content_type="application/json",
        ).status_code
        == 401
    )
    assert client.get(f"/api/automations/{uuid4()}").status_code == 401


@pytest.mark.django_db
def test_create_list_and_detail_automations_are_user_scoped(client):
    token = _register_and_token(client, "automation-api@example.com")
    other_token = _register_and_token(client, "automation-other@example.com")

    create_response = client.post(
        AUTOMATIONS_URL,
        data={"prompt": "  Summarize my day  ", "schedule_time": "09:30:00"},
        content_type="application/json",
        **_auth(token),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["prompt"] == "Summarize my day"
    assert created["schedule_time"] == "09:30:00"
    assert created["is_active"] is True

    list_response = client.get(AUTOMATIONS_URL, **_auth(token))
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert [row["id"] for row in list_response.json()["automations"]] == [created["id"]]

    detail_response = client.get(f"/api/automations/{created['id']}", **_auth(token))
    assert detail_response.status_code == 200
    assert detail_response.json()["prompt"] == "Summarize my day"

    other_detail = client.get(f"/api/automations/{created['id']}", **_auth(other_token))
    assert other_detail.status_code == 404


@pytest.mark.django_db
def test_list_includes_inactive_automations(client):
    token = _register_and_token(client, "automation-inactive@example.com")
    user = User.objects.get(email="automation-inactive@example.com")
    Automation.objects.create(
        user=user,
        prompt="Paused",
        schedule_time=datetime.time(10, 0),
        is_active=False,
    )

    response = client.get(AUTOMATIONS_URL, **_auth(token))

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["automations"][0]["is_active"] is False


@pytest.mark.django_db
def test_create_and_update_reject_blank_prompt(client):
    token = _register_and_token(client, "automation-blank@example.com")

    create_response = client.post(
        AUTOMATIONS_URL,
        data={"prompt": "   ", "schedule_time": "09:30:00"},
        content_type="application/json",
        **_auth(token),
    )
    assert create_response.status_code == 400

    ok_response = client.post(
        AUTOMATIONS_URL,
        data={"prompt": "Daily review", "schedule_time": "09:30:00"},
        content_type="application/json",
        **_auth(token),
    )
    assert ok_response.status_code == 201

    update_response = client.patch(
        f"/api/automations/{ok_response.json()['id']}",
        data={"prompt": "   "},
        content_type="application/json",
        **_auth(token),
    )
    assert update_response.status_code == 400


@pytest.mark.django_db
def test_update_and_delete_automation(client):
    token = _register_and_token(client, "automation-update@example.com")
    create_response = client.post(
        AUTOMATIONS_URL,
        data={"prompt": "Daily review", "schedule_time": "09:30:00"},
        content_type="application/json",
        **_auth(token),
    )
    automation_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/automations/{automation_id}",
        data={
            "prompt": "Evening review",
            "schedule_time": "18:00:00",
            "is_active": False,
        },
        content_type="application/json",
        **_auth(token),
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["prompt"] == "Evening review"
    assert updated["schedule_time"] == "18:00:00"
    assert updated["is_active"] is False

    delete_response = client.delete(f"/api/automations/{automation_id}", **_auth(token))
    assert delete_response.status_code == 204
    assert Automation.objects.filter(pk=automation_id).exists() is False

    missing_response = client.get(f"/api/automations/{automation_id}", **_auth(token))
    assert missing_response.status_code == 404
