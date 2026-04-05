from django.conf import settings
from django.db import models


class AgentRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class MessageActor(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    SYSTEM = "system", "System"
    TOOL_CALL = "tool_call", "Tool call"
    TOOL_RESULT = "tool_result", "Tool result"


class AgentRun(models.Model):
    channel = models.ForeignKey(
        "channels.Channel",
        on_delete=models.CASCADE,
        related_name="agent_runs",
    )
    conversation = models.ForeignKey(
        "channels.Conversation",
        on_delete=models.CASCADE,
        related_name="agent_runs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_runs",
    )
    model = models.CharField(
        max_length=128,
        help_text="LLM model identifier (e.g. gpt-4o, claude-3-5-sonnet).",
    )
    status = models.CharField(
        max_length=32,
        choices=AgentRunStatus.choices,
        default=AgentRunStatus.PENDING,
    )
    error = models.TextField(
        blank=True,
        help_text="Failure message or traceback when status is failed.",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["conversation"]),
        ]

    def __str__(self):
        return f"AgentRun({self.pk}, {self.status})"


class MessageLog(models.Model):
    agent_run = models.ForeignKey(
        AgentRun,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    conversation = models.ForeignKey(
        "channels.Conversation",
        on_delete=models.CASCADE,
        related_name="agent_message_logs",
    )
    channel = models.ForeignKey(
        "channels.Channel",
        on_delete=models.CASCADE,
        related_name="agent_message_logs",
    )
    actor = models.CharField(max_length=32, choices=MessageActor.choices)
    content = models.TextField(
        blank=True,
        help_text="Plain text or serialized tool args/result.",
    )
    tool_call_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="Pairs tool_call rows with tool_result rows for LLM APIs.",
    )
    tool_name = models.CharField(max_length=128, blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured extras (args, errors, provider-specific fields).",
    )
    input_tokens = models.IntegerField(
        null=True,
        blank=True,
        help_text="Input tokens for this message (typically assistant turns).",
    )
    output_tokens = models.IntegerField(
        null=True,
        blank=True,
        help_text="Output tokens for this message (typically assistant turns).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "-created_at"]),
            models.Index(fields=["channel", "-created_at"]),
            models.Index(fields=["agent_run", "created_at"]),
        ]

    def __str__(self):
        return f"MessageLog({self.pk}, actor={self.actor})"
