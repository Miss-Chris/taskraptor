import pytest

from apps.accounts.models import User
from apps.agent.models import UserProfile


@pytest.fixture
def user(db):
    account = User.objects.create_user(email="agent@example.com", password="hunter2!")
    UserProfile.objects.create(user=account, timezone="America/Toronto")
    return account


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="other-agent@example.com", password="hunter2!")
