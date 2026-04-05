from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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


class LlmProvider(models.TextChoices):
    ANTHROPIC = "anthropic", "Anthropic"
    SYSTEM_FREE = "system_free", "System free"


class LlmModelName(models.TextChoices):
    """Anthropic model IDs passed to litellm as anthropic/<id>."""

    CLAUDE_HAIKU = "claude-haiku-4-5-20251001", "Claude Haiku 4.5"
    CLAUDE_SONNET = "claude-sonnet-4-6", "Claude Sonnet 4.6"


class LlmModel(models.Model):
    """
    Per-user LLM configuration: Anthropic (BYO key) or system_free (server key + quota).
    API keys are stored as plain text; use encryption at rest in production if required.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="llm_models",
    )
    provider = models.CharField(max_length=32, choices=LlmProvider.choices)
    model_name = models.CharField(max_length=128, choices=LlmModelName.choices)
    api_key = models.TextField(
        blank=True,
        help_text="Anthropic API key; leave empty for system_free (uses SERVER_API_KEY).",
    )
    quota = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max usage units (total tokens) for system_free; null means unlimited.",
    )
    quota_used = models.PositiveIntegerField(
        default=0,
        help_text="Cumulative usage (total tokens) counted for system_free tier.",
    )
    quota_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When set, system_free quota is invalid after this time.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider"],
                condition=models.Q(provider=LlmProvider.SYSTEM_FREE),
                name="agent_llmmodel_unique_system_free_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "provider"]),
        ]

    def __str__(self):
        return f"LlmModel({self.pk}, {self.provider}, {self.model_name})"

    def clean(self):
        if self.provider == LlmProvider.SYSTEM_FREE:
            if (self.api_key or "").strip():
                raise ValidationError(
                    {"api_key": "Must be empty for system_free provider."},
                )
            if self.model_name != LlmModelName.CLAUDE_HAIKU:
                raise ValidationError(
                    {
                        "model_name": "system_free only supports Claude Haiku.",
                    },
                )
        elif self.provider == LlmProvider.ANTHROPIC:
            if not (self.api_key or "").strip():
                raise ValidationError(
                    {"api_key": "Anthropic provider requires an API key."},
                )

    def save(self, *args, **kwargs):
        if self.provider == LlmProvider.SYSTEM_FREE:
            self.model_name = LlmModelName.CLAUDE_HAIKU
            self.api_key = ""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_quota_exceeded(self) -> bool:
        if not self.is_active:
            return True
        now = timezone.now()
        if self.quota_expires_at is not None and now > self.quota_expires_at:
            return True
        if self.quota is not None and self.quota_used >= self.quota:
            return True
        return False


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
    llm_model = models.ForeignKey(
        LlmModel,
        on_delete=models.PROTECT,
        related_name="agent_runs",
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
