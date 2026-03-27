from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "status", "description", "due_at", "created_at"]
    list_filter = ["status", "user"]
    search_fields = ["description", "user__email"]
    ordering = ["-created_at"]
