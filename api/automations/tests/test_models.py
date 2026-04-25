"""Tests for automations models."""

from __future__ import annotations

import datetime

import pytest

from automations.models import Automation


@pytest.mark.django_db
def test_automation_defaults_and_str(test_user):
    t = datetime.time(9, 30)
    automation = Automation.objects.create(
        user=test_user,
        prompt="List my top 5 important tasks",
        schedule_time=t,
    )

    assert automation.is_active is True
    assert automation.prompt == "List my top 5 important tasks"
    assert automation.schedule_time == t
    assert automation.user_id == test_user.pk
    assert "Automation(" in str(automation)


@pytest.mark.django_db
def test_user_timezone_default(test_user):
    assert test_user.timezone is None


@pytest.mark.django_db
def test_user_timezone_custom(test_user):
    test_user.timezone = "America/New_York"
    test_user.save(update_fields=["timezone"])
    test_user.refresh_from_db()
    assert test_user.timezone == "America/New_York"
