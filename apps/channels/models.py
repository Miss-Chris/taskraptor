import secrets

from django.conf import settings
from django.db import models


def _generate_join_code() -> str:
    return secrets.token_urlsafe(16)


class TelegramChannel(models.Model):
    """
    Links a Telegram chat to a TaskRaptor user account.
    Populated during the JOIN flow (M2).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_channel",
    )
    # Set once the user completes the JOIN flow.
    chat_id = models.BigIntegerField(null=True, blank=True, unique=True)
    join_code = models.CharField(max_length=64, default=_generate_join_code, unique=True)
    linked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"TelegramChannel({self.user.email}, linked={self.linked_at is not None})"
