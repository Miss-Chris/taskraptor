import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from channels.models import Channel, ChannelType, TelegramJoinCode

REGISTER_URL = "/api/auth/register"
STATUS_URL = "/api/telegram/status"
JOIN_CODE_URL = "/api/telegram/join-code"


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
def test_telegram_status_unauthenticated(client):
    response = client.get(STATUS_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_telegram_status_invalid_token(client):
    response = client.get(
        STATUS_URL,
        HTTP_AUTHORIZATION="Bearer 00000000-0000-0000-0000-000000000000",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_telegram_status_not_connected(client):
    token = _register_and_token(client, "tg1@example.com")
    response = client.get(STATUS_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert "bot_name" in data


@pytest.mark.django_db
def test_telegram_status_connected(client):
    token = _register_and_token(client, "tg2@example.com")
    user = User.objects.get(email="tg2@example.com")
    Channel.objects.create(
        user=user,
        name="Telegram",
        type=ChannelType.TELEGRAM,
        external_id="12345",
    )

    response = client.get(STATUS_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    assert response.json()["connected"] is True


@pytest.mark.django_db
def test_telegram_join_code_unauthenticated(client):
    response = client.post(JOIN_CODE_URL, content_type="application/json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_telegram_join_code_success(client):
    token = _register_and_token(client, "tg3@example.com")
    response = client.post(
        JOIN_CODE_URL,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["code"]) == 6
    assert "expires_at" in data
    assert "bot_name" in data


@pytest.mark.django_db
def test_telegram_join_code_regenerates_invalidates_previous(client):
    token = _register_and_token(client, "tg4@example.com")
    user = User.objects.get(email="tg4@example.com")

    r1 = client.post(
        JOIN_CODE_URL,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r1.status_code == 200
    first_code = r1.json()["code"]

    row1 = TelegramJoinCode.objects.get(code=first_code)
    assert row1.redeemed_at is None
    assert row1.expires_at > timezone.now()

    r2 = client.post(
        JOIN_CODE_URL,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert r2.status_code == 200
    second_code = r2.json()["code"]
    assert second_code != first_code

    row1.refresh_from_db()
    assert row1.expires_at <= timezone.now()
