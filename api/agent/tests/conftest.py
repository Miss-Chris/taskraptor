from __future__ import annotations

import pytest
from decouple import UndefinedValueError, config
from django.contrib.auth import get_user_model

from agent.models import LlmModel, LlmModelName, LlmProvider

User = get_user_model()


@pytest.fixture(scope="session")
def test_api_key():
    """
    Read TEST_ANTHROPIC_API_KEY from the environment or .env file.
    Skips any test that uses this fixture if the key is absent.
    """
    try:
        key = config("TEST_ANTHROPIC_API_KEY")
        if not key or not key.strip():
            pytest.skip("TEST_ANTHROPIC_API_KEY is not set")
        return key.strip()
    except UndefinedValueError:
        pytest.skip("TEST_ANTHROPIC_API_KEY is not set")


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="agent_test_user",
        email="agent_test@example.com",
        password="testpass123",
    )


@pytest.fixture
def test_llm_model(test_user, test_api_key):
    return LlmModel.objects.create(
        user=test_user,
        provider=LlmProvider.ANTHROPIC,
        model_name=LlmModelName.CLAUDE_HAIKU,
        api_key=test_api_key,
    )
