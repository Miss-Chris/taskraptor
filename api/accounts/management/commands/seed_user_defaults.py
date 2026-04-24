from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import User
from accounts.services import seed_default_user_data


class Command(BaseCommand):
    help = "Seed default tags and automations for existing users."

    def handle(self, *args, **options):
        users = User.objects.order_by("email")
        user_count = 0
        tags_created = 0
        automations_created = 0

        for user in users.iterator():
            result = seed_default_user_data(user)
            user_count += 1
            tags_created += result.tags_created
            automations_created += result.automations_created

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded defaults for "
                f"{user_count} users: "
                f"{tags_created} tags, "
                f"{automations_created} automations created."
            )
        )
