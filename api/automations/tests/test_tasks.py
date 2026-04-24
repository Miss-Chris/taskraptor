from __future__ import annotations

import datetime
from uuid import UUID

import pytest
from django.utils import timezone

from automations.models import Automation
from automations.tasks import dispatch_due_automations, run_automation
from channels.models import Channel, ChannelType


@pytest.mark.django_db
def test_dispatch_due_automations_enqueues_only_due_rows(monkeypatch, test_user):
    channel = Channel.objects.create(
        user=test_user,
        name="Web",
        type=ChannelType.WEB,
    )
    now = datetime.datetime(2026, 4, 5, 15, 0, tzinfo=datetime.UTC)
    queued_ids: list[str] = []

    due = Automation.objects.create(
        user=test_user,
        channel=channel,
        prompt="Run now",
        schedule_time=datetime.time(14, 0),
    )
    Automation.objects.create(
        user=test_user,
        channel=channel,
        prompt="Too early",
        schedule_time=datetime.time(16, 0),
    )
    Automation.objects.create(
        user=test_user,
        channel=channel,
        prompt="Already ran",
        schedule_time=datetime.time(13, 0),
        last_run_at=now - datetime.timedelta(hours=1),
    )

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)
    monkeypatch.setattr(run_automation, "delay", queued_ids.append)

    queued = dispatch_due_automations()

    assert queued == 1
    assert queued_ids == [str(due.pk)]


@pytest.mark.django_db
def test_run_automation_executes_and_marks_last_run_at(monkeypatch, test_user):
    channel = Channel.objects.create(
        user=test_user,
        name="Web",
        type=ChannelType.WEB,
    )
    automation = Automation.objects.create(
        user=test_user,
        channel=channel,
        prompt="Run automation",
        schedule_time=datetime.time(9, 0),
    )
    now = datetime.datetime(2026, 4, 5, 15, 0, tzinfo=datetime.UTC)
    calls: list[tuple[UUID, str]] = []

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)
    monkeypatch.setattr(
        "automations.tasks.handle_system_message",
        lambda channel, prompt: calls.append((channel.pk, prompt)),
    )

    ran = run_automation(automation.pk)

    automation.refresh_from_db()
    assert ran is True
    assert calls == [(channel.pk, "Run automation")]
    assert automation.last_run_at == now


@pytest.mark.django_db
def test_run_automation_skips_when_already_run_today_in_user_timezone(
    monkeypatch,
    test_user,
):
    test_user.timezone = "America/New_York"
    test_user.save(update_fields=["timezone"])
    channel = Channel.objects.create(
        user=test_user,
        name="Web",
        type=ChannelType.WEB,
    )
    now = datetime.datetime(2026, 4, 5, 15, 0, tzinfo=datetime.UTC)
    automation = Automation.objects.create(
        user=test_user,
        channel=channel,
        prompt="Already handled",
        schedule_time=datetime.time(9, 0),
        last_run_at=datetime.datetime(2026, 4, 5, 13, 30, tzinfo=datetime.UTC),
    )
    called = False

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)

    def _unexpected_call(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("automations.tasks.handle_system_message", _unexpected_call)

    ran = run_automation(automation.pk)

    assert ran is False
    assert called is False


@pytest.mark.django_db
def test_automation_runs_at_user_local_wall_clock_time(monkeypatch, test_user):
    test_user.timezone = "America/Los_Angeles"
    test_user.save(update_fields=["timezone"])
    channel = Channel.objects.create(
        user=test_user,
        name="Web",
        type=ChannelType.WEB,
    )
    automation = Automation.objects.create(
        user=test_user,
        channel=channel,
        prompt="Local 9am",
        schedule_time=datetime.time(9, 0),
    )
    now = datetime.datetime(2026, 4, 5, 16, 0, tzinfo=datetime.UTC)

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: now)
    monkeypatch.setattr("automations.tasks.handle_system_message", lambda *_: None)

    assert run_automation(automation.pk) is True


@pytest.mark.django_db
def test_automation_dst_fall_back_does_not_double_run_same_local_day(
    monkeypatch,
    test_user,
):
    test_user.timezone = "America/New_York"
    test_user.save(update_fields=["timezone"])
    channel = Channel.objects.create(
        user=test_user,
        name="Web",
        type=ChannelType.WEB,
    )
    automation = Automation.objects.create(
        user=test_user,
        channel=channel,
        prompt="DST",
        schedule_time=datetime.time(1, 30),
        last_run_at=datetime.datetime(2026, 11, 1, 5, 35, tzinfo=datetime.UTC),
    )
    second_130 = datetime.datetime(2026, 11, 1, 6, 35, tzinfo=datetime.UTC)
    called = False

    monkeypatch.setattr("automations.tasks.timezone.now", lambda: second_130)

    def _unexpected_call(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("automations.tasks.handle_system_message", _unexpected_call)

    assert run_automation(automation.pk) is False
    assert called is False
