from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from accounts.models import User
from automations.models import Automation
from tasks.models import UserTag

DEFAULT_TAGS: tuple[str, ...] = ("work", "personal", "family")

MORNING_CHECKIN_PROMPT = (
    "Morning check-in: review my open tasks and tell me what to focus on today."
)
MIDDAY_CHECKIN_PROMPT = (
    "Midday check-in: review my open tasks and suggest what to tackle next."
)

DEFAULT_AUTOMATIONS: tuple[dict[str, object], ...] = (
    {
        "prompt": MORNING_CHECKIN_PROMPT,
        "schedule_time": time(9, 0),
        "is_active": True,
    },
    {
        "prompt": MIDDAY_CHECKIN_PROMPT,
        "schedule_time": time(13, 0),
        "is_active": False,
    },
)


@dataclass(frozen=True)
class DefaultSeedResult:
    tags_created: int = 0
    automations_created: int = 0


def seed_default_user_data(user: User) -> DefaultSeedResult:
    tags_created = seed_default_tags(user)
    automations_created = seed_default_automations(user)
    return DefaultSeedResult(
        tags_created=tags_created,
        automations_created=automations_created,
    )


def seed_default_tags(user: User) -> int:
    created = 0
    existing = set(
        UserTag.objects.filter(user=user, name__in=DEFAULT_TAGS).values_list(
            "name",
            flat=True,
        )
    )

    rows = []
    for sort_order, name in enumerate(DEFAULT_TAGS):
        if name not in existing:
            rows.append(UserTag(user=user, name=name, sort_order=sort_order))
            created += 1

    if rows:
        UserTag.objects.bulk_create(rows)
    return created


def seed_default_automations(user: User) -> int:
    created = 0
    for default in DEFAULT_AUTOMATIONS:
        automation, was_created = Automation.objects.get_or_create(
            user=user,
            prompt=default["prompt"],
            schedule_time=default["schedule_time"],
            defaults={"is_active": default["is_active"]},
        )
        if was_created:
            created += 1
    return created
