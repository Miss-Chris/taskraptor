import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_health_returns_ok_when_database_is_available(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_unavailable_when_database_check_fails(client, monkeypatch):
    monkeypatch.setattr("taskraptor.api._database_is_healthy", lambda: False)

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}
