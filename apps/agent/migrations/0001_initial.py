import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("trigger_message", models.TextField()),
                (
                    "trigger_type",
                    models.CharField(
                        choices=[("user", "User"), ("schedule", "Schedule"), ("alarm", "Alarm")],
                        max_length=20,
                    ),
                ),
                (
                    "stopped_reason",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("completed", "Completed"),
                            ("max_iterations", "Max Iterations"),
                            ("max_respond_calls", "Max Respond Calls"),
                            ("error", "Error"),
                        ],
                        max_length=30,
                    ),
                ),
                ("model_used", models.CharField(max_length=100)),
                ("input_tokens", models.IntegerField(default=0)),
                ("output_tokens", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("preferences", models.JSONField(default=dict)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ToolCall",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("index", models.IntegerField()),
                ("tool_name", models.CharField(max_length=100)),
                ("tool_input", models.JSONField()),
                ("tool_output", models.JSONField()),
                ("summary", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "agent_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tool_calls",
                        to="agent.agentrun",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tool_calls",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["index"]},
        ),
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "role",
                    models.CharField(
                        choices=[("user", "User"), ("assistant", "Assistant")],
                        max_length=10,
                    ),
                ),
                ("content", models.TextField()),
                ("index", models.IntegerField(blank=True, null=True)),
                ("channel", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "agent_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="messages",
                        to="agent.agentrun",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_messages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
