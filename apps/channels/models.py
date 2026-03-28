import secrets

from django.conf import settings
from django.db import models


def _generate_join_code() -> str:
    return secrets.token_urlsafe(16)


class ChannelType(models.TextChoices):
    TELEGRAM = "telegram", "Telegram"


class ChannelRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    FULFILLED = "fulfilled", "Fulfilled"
    EXPIRED = "expired", "Expired"


class ChannelRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="channel_requests",
    )
    channel_type = models.CharField(
        max_length=32,
        choices=ChannelType.choices,
        default=ChannelType.TELEGRAM,
    )
    join_code = models.CharField(max_length=64, default=_generate_join_code, unique=True)
    status = models.CharField(
        max_length=20,
        choices=ChannelRequestStatus.choices,
        default=ChannelRequestStatus.PENDING,
    )
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ChannelRequest({self.user.email}, {self.channel_type}, {self.status})"


class Channel(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="channels",
    )
    channel_type = models.CharField(
        max_length=32,
        choices=ChannelType.choices,
        default=ChannelType.TELEGRAM,
    )
    telegram_chat_id = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_username = models.CharField(max_length=255, null=True, blank=True)
    connected_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "channel_type"],
                name="unique_channel_per_user_and_type",
            ),
        ]

    def __str__(self) -> str:
        return f"Channel({self.user.email}, {self.channel_type})"
