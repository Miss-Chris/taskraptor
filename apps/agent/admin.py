from django.contrib import admin

from .models import AgentRun, ChatMessage, Schedule, Todo, ToolCall, UserProfile


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "priority", "is_completed", "due_date", "created_at"]
    list_filter = ["priority", "is_completed"]
    search_fields = ["title", "notes"]


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "trigger_type", "stopped_reason", "model_used", "input_tokens", "output_tokens", "created_at"]
    list_filter = ["trigger_type", "stopped_reason"]


@admin.register(ToolCall)
class ToolCallAdmin(admin.ModelAdmin):
    list_display = ["tool_name", "user", "agent_run", "index", "summary", "created_at"]
    list_filter = ["tool_name"]
    search_fields = ["summary"]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ["role", "user", "channel", "content_preview", "created_at"]
    list_filter = ["role", "channel"]

    @admin.display(description="Content")
    def content_preview(self, obj):
        return obj.content[:80]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["instruction_preview", "user", "is_recurring", "is_active", "next_run_at"]
    list_filter = ["is_recurring", "is_active"]

    @admin.display(description="Instruction")
    def instruction_preview(self, obj):
        return obj.instruction[:60]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "timezone"]
