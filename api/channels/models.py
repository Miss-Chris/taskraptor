from django.conf import settings
from django.db import models


class WebChatRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


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
        constraints = [
            models.UniqueConstraint(
                fields=["user", "type"],
                condition=models.Q(type=ChannelType.WEB),
                name="channels_channel_unique_web_per_user",
            ),
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


class WebChatMessage(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="web_messages",
    )
    role = models.CharField(max_length=16, choices=WebChatRole.choices)
    content = models.TextField()
    agent_run = models.ForeignKey(
        "agent.AgentRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="web_messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"WebChatMessage({self.pk}, role={self.role})"
