from __future__ import annotations

import enum
import uuid

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


class LlmProvider(str, enum.Enum):
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    SYSTEM_FREE = "system_free"


SUPPORTED_MODEL_KEYS: frozenset[str] = frozenset(
    {
        "anthropic/claude-haiku-4-5-20251001",
        "anthropic/claude-sonnet-4-6",
        "deepseek/deepseek-chat",  # DeepSeek v3
        "system_free",  # server-managed DeepSeek key with quota
    }
)

SYSTEM_FREE_MODEL_KEY = "system_free"
SYSTEM_FREE_UNDERLYING_MODEL = "deepseek/deepseek-chat"


class LlmModel(models.Model):
    """
    Per-user LLM configuration.

    ``model_key`` is the litellm model identifier, e.g. ``deepseek/deepseek-chat``
    or the special value ``system_free`` which routes to DeepSeek using the
    server-managed ``DEEPSEEK_API_KEY`` with a per-user quota.

    API keys are stored as plain text; use encryption at rest in production if
    required.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="llm_models",
    )
    model_key = models.CharField(
        max_length=128,
        default=SYSTEM_FREE_MODEL_KEY,
        help_text=(
            "litellm model key, e.g. 'deepseek/deepseek-chat', or 'system_free' "
            "to use the server-managed DeepSeek key with quota."
        ),
    )
    api_key = models.TextField(
        blank=True,
        help_text="Provider API key; leave empty for system_free (uses DEEPSEEK_API_KEY).",
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
    context_message_limit = models.PositiveIntegerField(
        default=25,
        help_text=(
            "Maximum number of prior history messages included in each LLM request. "
            "Lower values reduce cost; higher values improve context quality. Range: 1–1024."
        ),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "model_key"],
                condition=models.Q(model_key=SYSTEM_FREE_MODEL_KEY),
                name="agent_llmmodel_unique_system_free_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "model_key"]),
        ]

    def __str__(self) -> str:
        return f"LlmModel({self.pk}, {self.model_key})"

    def clean(self) -> None:
        if self.model_key not in SUPPORTED_MODEL_KEYS:
            raise ValidationError(
                {"model_key": f"Unsupported model_key {self.model_key!r}. "
                 f"Supported: {sorted(SUPPORTED_MODEL_KEYS)}"},
            )
        if self.model_key == SYSTEM_FREE_MODEL_KEY and (self.api_key or "").strip():
            raise ValidationError(
                {"api_key": "Must be empty for system_free (uses server DEEPSEEK_API_KEY)."},
            )
        if self.context_message_limit < 1 or self.context_message_limit > 1024:
            raise ValidationError(
                {"context_message_limit": "Must be between 1 and 1024."},
            )

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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    def __str__(self) -> str:
        return f"AgentRun({self.pk}, {self.status})"


class MessageLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    def __str__(self) -> str:
        return f"MessageLog({self.pk}, actor={self.actor})"
