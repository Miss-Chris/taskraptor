from django.conf import settings
from django.db import models


class ChannelType(models.TextChoices):
    TELEGRAM = "telegram", "Telegram"
    WEB = "web", "Web"
    DUMMY = "dummy", "Dummy"


class Channel(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="channels",
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=32, choices=ChannelType.choices)
    external_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return self.name


class Conversation(models.Model):
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    external_id = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["channel", "-updated_at"]),
        ]

    def __str__(self):
        return f"Conversation({self.pk}, channel={self.channel_id})"
