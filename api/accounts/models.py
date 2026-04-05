import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    timezone = models.CharField(
        max_length=63,
        default="UTC",
        help_text="IANA timezone name (e.g. America/New_York) for scheduling automations.",
    )
    prompt_instructions = models.TextField(
        blank=True,
        default="",
        help_text="Additional standing instructions appended to the assistant system prompt for all of this user's runs.",
    )

    class Meta:
        db_table = "auth_user"


class UserSession(models.Model):
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "auth_user_session"

    def __str__(self):
        return f"Session({self.user_id}, {self.token})"

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()
