import uuid

from django.conf import settings
from django.db import models


class Automation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="automations",
    )
    channel = models.ForeignKey(
        "channels.Channel",
        on_delete=models.CASCADE,
        related_name="automations",
    )
    prompt = models.TextField(
        help_text=(
            "The prompt to send as a system message, e.g. 'List my top 5 important tasks'."
        ),
    )
    schedule_time = models.TimeField(
        help_text="Time of day in the user's local timezone when this automation runs.",
    )
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Most recent successful run timestamp in UTC.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["channel"]),
        ]

    def __str__(self) -> str:
        return f"Automation({self.pk}, user={self.user_id}, active={self.is_active})"
