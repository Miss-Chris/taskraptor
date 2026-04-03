import uuid

from django.conf import settings
from django.db import models


class Todo(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todos"
    )
    title = models.CharField(max_length=500)
    notes = models.TextField(blank=True, default="")
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )
    tags = models.JSONField(default=list)
    is_completed = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True)
    alarm_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class AgentRun(models.Model):
    class TriggerType(models.TextChoices):
        USER = "user", "User"
        SCHEDULE = "schedule", "Schedule"
        ALARM = "alarm", "Alarm"

    class StoppedReason(models.TextChoices):
        COMPLETED = "completed", "Completed"
        MAX_ITERATIONS = "max_iterations", "Max Iterations"
        MAX_RESPOND_CALLS = "max_respond_calls", "Max Respond Calls"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_runs"
    )
    trigger_message = models.TextField()
    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices)
    stopped_reason = models.CharField(
        max_length=30, choices=StoppedReason.choices, blank=True
    )
    model_used = models.CharField(max_length=100)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Run {self.id} ({self.trigger_type})"


class ToolCall(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tool_calls"
    )
    agent_run = models.ForeignKey(
        AgentRun, on_delete=models.CASCADE, related_name="tool_calls"
    )
    index = models.IntegerField()
    tool_name = models.CharField(max_length=100)
    tool_input = models.JSONField()
    tool_output = models.JSONField()
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["index"]

    def __str__(self):
        return f"{self.tool_name} (run {self.agent_run_id}, idx {self.index})"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages"
    )
    agent_run = models.ForeignKey(
        AgentRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    index = models.IntegerField(null=True, blank=True)
    channel = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class Schedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="schedules"
    )
    instruction = models.TextField()
    cron_expression = models.CharField(max_length=100, blank=True)
    is_recurring = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(db_index=True)
    related_todo = models.ForeignKey(
        Todo, on_delete=models.SET_NULL, null=True, blank=True, related_name="schedules"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["next_run_at"]

    def __str__(self):
        return f"Schedule: {self.instruction[:50]}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    timezone = models.CharField(max_length=64, default="UTC")
    preferences = models.JSONField(default=dict)

    def __str__(self):
        return f"Profile({self.user_id})"
