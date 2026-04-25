import pytest
from django.contrib.auth import get_user_model


User = get_user_model()


@pytest.mark.django_db
def test_user_timezone_defaults_to_none():
    user = User.objects.create_user(
        email="timezone_default@example.com",
        password="testpass123",
    )

    assert user.timezone is None


@pytest.mark.django_db
def test_user_prompt_instructions_defaults_to_empty_string():
    user = User.objects.create_user(
        email="prompt_default@example.com",
        password="testpass123",
    )

    assert user.prompt_instructions == ""


@pytest.mark.django_db
def test_user_prompt_instructions_persists_custom_value():
    user = User.objects.create_user(
        email="prompt_custom@example.com",
        password="testpass123",
        prompt_instructions="Always format due dates as YYYY-MM-DD.",
    )

    user.refresh_from_db()

    assert user.prompt_instructions == "Always format due dates as YYYY-MM-DD."
