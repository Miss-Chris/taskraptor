import pytest
from django.test import Client


@pytest.fixture
def anon_client() -> Client:
    """Django test client with CSRF checks disabled (mirrors browser behaviour
    where the CSRF cookie is present but we don't want to manually thread it
    through every test helper call)."""
    return Client(enforce_csrf_checks=False)
