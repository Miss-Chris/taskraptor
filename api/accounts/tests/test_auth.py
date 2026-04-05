from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import UserSession

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_register_success(client):
    response = client.post(
        REGISTER_URL,
        data={"username": "alice", "email": "alice@example.com", "password": "secret123"},
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
def test_register_duplicate_username(client):
    payload = {"username": "bob", "email": "bob@example.com", "password": "secret123"}
    client.post(REGISTER_URL, data=payload, content_type="application/json")
    response = client.post(REGISTER_URL, data=payload, content_type="application/json")
    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.django_db
def test_login_success(client):
    client.post(
        REGISTER_URL,
        data={"username": "carol", "email": "carol@example.com", "password": "secret123"},
        content_type="application/json",
    )
    response = client.post(
        LOGIN_URL,
        data={"username": "carol", "password": "secret123"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "token" in response.json()


@pytest.mark.django_db
def test_login_wrong_password(client):
    client.post(
        REGISTER_URL,
        data={"username": "dave", "email": "dave@example.com", "password": "secret123"},
        content_type="application/json",
    )
    response = client.post(
        LOGIN_URL,
        data={"username": "dave", "password": "wrongpassword"},
        content_type="application/json",
    )
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.django_db
def test_me_authenticated(client):
    reg = client.post(
        REGISTER_URL,
        data={"username": "eve", "email": "eve@example.com", "password": "secret123"},
        content_type="application/json",
    )
    token = reg.json()["token"]

    response = client.get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "eve"
    assert data["email"] == "eve@example.com"
    assert "id" in data
    assert "date_joined" in data


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
        data={"username": "frank", "email": "frank@example.com", "password": "secret123"},
        content_type="application/json",
    )
    token = reg.json()["token"]
    UserSession.objects.filter(token=token).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    response = client.get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401
