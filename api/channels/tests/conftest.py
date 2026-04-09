from __future__ import annotations

import pytest
from decouple import UndefinedValueError, config
from django.contrib.auth import get_user_model

from agent.models import LlmModel
from channels.models import Channel, ChannelType, Conversation

User = get_user_model()


@pytest.fixture(scope="session")
def test_api_key():
    """
    Read TEST_DEEPSEEK_API_KEY from the environment or .env file.
    Skips any test that uses this fixture if the key is absent.
    """
    try:
        key = config("TEST_DEEPSEEK_API_KEY")
        if not key or not key.strip():
            pytest.skip("TEST_DEEPSEEK_API_KEY is not set")
        return key.strip()
    except UndefinedValueError:
        pytest.skip("TEST_DEEPSEEK_API_KEY is not set")


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        email="workflow_test@example.com",
        password="testpass123",
    )


@pytest.fixture
def test_llm_model(test_user, test_api_key):
    return LlmModel.objects.create(
        user=test_user,
        model_key="deepseek/deepseek-chat",
        api_key=test_api_key,
    )


@pytest.fixture
def test_llm_model_offline(test_user):
    """LlmModel fixture that requires no real API key -- for scripted/offline tests."""
    return LlmModel.objects.create(
        user=test_user,
        model_key="deepseek/deepseek-chat",
        api_key="sk-fake-never-used",
    )


@pytest.fixture
def test_channel(test_user):
    return Channel.objects.create(
        user=test_user,
        name="Test Dummy Channel",
        type=ChannelType.DUMMY,
    )


@pytest.fixture
def test_conversation(test_channel):
    return Conversation.objects.create(
        channel=test_channel,
        title="Test Conversation",
    )
