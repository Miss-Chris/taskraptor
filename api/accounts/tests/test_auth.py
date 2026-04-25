from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from accounts.models import UserSession
from accounts.services import (
    MIDDAY_CHECKIN_PROMPT,
    MORNING_CHECKIN_PROMPT,
    seed_default_user_data,
)
from agent.models import LlmModel, SYSTEM_FREE_MODEL_KEY
from automations.models import Automation
from tasks.models import UserTag

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"
TIMEZONE_URL = "/api/auth/me/timezone"


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_register_success(client):
    response = client.post(
        REGISTER_URL,
        data={"email": "alice@example.com", "password": "secret123"},
        content_type="application/json",
    )
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert len(data["token"]) == 36  # UUID format
    session = UserSession.objects.get(token=data["token"])
    assert session.expires_at is not None
    assert session.expires_at > timezone.now()


@pytest.mark.django_db
def test_register_creates_system_free_model(client):
    response = client.post(
        REGISTER_URL,
        data={"email": "newuser@example.com", "password": "secret123"},
        content_type="application/json",
    )
    assert response.status_code == 201
    token = response.json()["token"]
    session = UserSession.objects.get(token=token)
    model = LlmModel.objects.filter(
        user=session.user, model_key=SYSTEM_FREE_MODEL_KEY
    ).first()
    assert model is not None
    assert model.is_active is True
    assert model.quota == 50


@pytest.mark.django_db
def test_register_creates_default_tags_and_automations(client):
    response = client.post(
        REGISTER_URL,
        data={"email": "defaults@example.com", "password": "secret123"},
        content_type="application/json",
    )

    assert response.status_code == 201
    session = UserSession.objects.get(token=response.json()["token"])
    assert list(
        UserTag.objects.filter(user=session.user).order_by("sort_order").values_list(
            "name",
            flat=True,
        )
    ) == ["work", "personal", "family"]

    automations = {
        automation.prompt: automation
        for automation in Automation.objects.filter(user=session.user)
    }
    assert set(automations) == {MORNING_CHECKIN_PROMPT, MIDDAY_CHECKIN_PROMPT}
    assert automations[MORNING_CHECKIN_PROMPT].schedule_time.isoformat() == "09:00:00"
    assert automations[MORNING_CHECKIN_PROMPT].is_active is True
    assert automations[MIDDAY_CHECKIN_PROMPT].schedule_time.isoformat() == "13:00:00"
    assert automations[MIDDAY_CHECKIN_PROMPT].is_active is False


@pytest.mark.django_db
def test_seed_default_user_data_is_idempotent():
    from accounts.models import User

    user = User.objects.create_user("seed-idempotent@example.com", "secret123")

    first = seed_default_user_data(user)
    second = seed_default_user_data(user)

    assert first.tags_created == 3
    assert first.automations_created == 2
    assert second.tags_created == 0
    assert second.automations_created == 0
    assert UserTag.objects.filter(user=user).count() == 3
    assert Automation.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_seed_user_defaults_command_seeds_existing_users_idempotently():
    from accounts.models import User

    User.objects.create_user("backfill-a@example.com", "secret123")
    User.objects.create_user("backfill-b@example.com", "secret123")
    out = StringIO()

    call_command("seed_user_defaults", stdout=out)
    call_command("seed_user_defaults", stdout=out)

    assert UserTag.objects.count() == 6
    assert Automation.objects.count() == 4
    assert "6 tags, 4 automations created" in out.getvalue()
    assert "0 tags, 0 automations created" in out.getvalue()


@pytest.mark.django_db
def test_register_duplicate_email(client):
    payload = {"email": "bob@example.com", "password": "secret123"}
    client.post(REGISTER_URL, data=payload, content_type="application/json")
    response = client.post(REGISTER_URL, data=payload, content_type="application/json")
    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.django_db
def test_login_success(client):
    client.post(
        REGISTER_URL,
        data={"email": "carol@example.com", "password": "secret123"},
        content_type="application/json",
    )
    response = client.post(
        LOGIN_URL,
        data={"email": "carol@example.com", "password": "secret123"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "token" in response.json()


@pytest.mark.django_db
def test_login_wrong_password(client):
    client.post(
        REGISTER_URL,
        data={"email": "dave@example.com", "password": "secret123"},
        content_type="application/json",
    )
    response = client.post(
        LOGIN_URL,
        data={"email": "dave@example.com", "password": "wrongpassword"},
        content_type="application/json",
    )
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.django_db
def test_me_authenticated(client):
    reg = client.post(
        REGISTER_URL,
        data={"email": "eve@example.com", "password": "secret123"},
        content_type="application/json",
    )
    token = reg.json()["token"]

    response = client.get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "eve@example.com"
    assert data["timezone"] == "UTC"
    assert "id" in data
    assert "date_joined" in data


@pytest.mark.django_db
def test_update_timezone_success(client):
    reg = client.post(
        REGISTER_URL,
        data={"email": "tz@example.com", "password": "secret123"},
        content_type="application/json",
    )
    token = reg.json()["token"]

    response = client.patch(
        TIMEZONE_URL,
        data={"timezone": "America/Toronto"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 200
    assert response.json()["timezone"] == "America/Toronto"


@pytest.mark.django_db
def test_update_timezone_rejects_invalid_timezone(client):
    reg = client.post(
        REGISTER_URL,
        data={"email": "bad-tz@example.com", "password": "secret123"},
        content_type="application/json",
    )
    token = reg.json()["token"]

    response = client.patch(
        TIMEZONE_URL,
        data={"timezone": "Not/AZone"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid IANA timezone."


@pytest.mark.django_db
def test_me_unauthenticated(client):
    response = client.get(ME_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_me_invalid_token(client):
    response = client.get(
        ME_URL,
        HTTP_AUTHORIZATION="Bearer 00000000-0000-0000-0000-000000000000",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_me_expired_token_rejected(client):
    reg = client.post(
        REGISTER_URL,
        data={"email": "frank@example.com", "password": "secret123"},
        content_type="application/json",
    )
    token = reg.json()["token"]
    UserSession.objects.filter(token=token).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    response = client.get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401
