from django.contrib import admin

from .models import AgentRun, ChatMessage, ToolCall, UserProfile


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "trigger_type", "model_used", "created_at")
    list_filter = ("trigger_type", "model_used")
    search_fields = ("trigger_message", "user__email")


@admin.register(ToolCall)
class ToolCallAdmin(admin.ModelAdmin):
    list_display = ("tool_name", "user", "agent_run", "index", "created_at")
    list_filter = ("tool_name",)
    search_fields = ("tool_name", "summary", "user__email")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("role", "user", "channel", "created_at")
    list_filter = ("role", "channel")
    search_fields = ("content", "user__email")
    ordering = ("-created_at",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone")
    search_fields = ("user__email", "timezone")
