import uuid

from django.conf import settings
from django.db import models


class DueType(models.TextChoices):
    DATE = "date", "Date"
    TIME = "time", "Time"


class TaskStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class AuditAction(models.TextChoices):
    STATUS_CHANGED = "status_changed", "Status changed"
    NAME_CHANGED = "name_changed", "Name changed"
    PRIORITY_CHANGED = "priority_changed", "Priority changed"
    TAGS_CHANGED = "tags_changed", "Tags changed"
    DELETED = "deleted", "Deleted"


class UserTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_tags",
    )
    name = models.CharField(max_length=64)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="tasks_usertag_user_name_uniq",
            ),
        ]

    def __str__(self):
        return self.name


def _normalize_tags(tags):
    """Compare tags as sorted strings; treats non-list JSON as empty."""
    if tags is None:
        return ()
    if not isinstance(tags, (list, tuple)):
        return ()
    return tuple(sorted(str(t) for t in tags))


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
    )
    priority = models.IntegerField(default=0)
    due_at = models.DateTimeField(null=True, blank=True)
    due_type = models.CharField(
        max_length=16,
        choices=DueType.choices,
        default=DueType.TIME,
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON array of tag strings.",
    )
    remind_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "deleted_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Optional actor for audit rows; also accepted via kwargs by callers.
        audit_actor = kwargs.pop("audit_actor", None)
        audit_actor_id = kwargs.pop("audit_actor_id", None)
        if audit_actor_id is None and audit_actor is not None:
            audit_actor_id = getattr(audit_actor, "pk", None)
        update_fields = kwargs.get("update_fields")

        tracked = {"status", "name", "priority", "tags"}
        if update_fields is not None:
            tracked &= set(update_fields)

        old_row = None
        if self.pk and tracked:
            old_row = (
                Task.objects.filter(pk=self.pk)
                .values("status", "name", "priority", "tags")
                .first()
            )

        super().save(*args, **kwargs)

        if old_row is None or not tracked:
            return

        logs = []
        if "status" in tracked and old_row["status"] != self.status:
            logs.append(
                TaskAuditLog(
                    task=self,
                    action=AuditAction.STATUS_CHANGED,
                    old_value=old_row["status"],
                    new_value=self.status,
                    actor_id=audit_actor_id,
                )
            )
        if "name" in tracked and old_row["name"] != self.name:
            logs.append(
                TaskAuditLog(
                    task=self,
                    action=AuditAction.NAME_CHANGED,
                    old_value=old_row["name"],
                    new_value=self.name,
                    actor_id=audit_actor_id,
                )
            )
        if "priority" in tracked and old_row["priority"] != self.priority:
            logs.append(
                TaskAuditLog(
                    task=self,
                    action=AuditAction.PRIORITY_CHANGED,
                    old_value=old_row["priority"],
                    new_value=self.priority,
                    actor_id=audit_actor_id,
                )
            )
        if "tags" in tracked and _normalize_tags(
            old_row["tags"]
        ) != _normalize_tags(self.tags):
            logs.append(
                TaskAuditLog(
                    task=self,
                    action=AuditAction.TAGS_CHANGED,
                    old_value=list(old_row["tags"])
                    if isinstance(old_row["tags"], list)
                    else old_row["tags"],
                    new_value=list(self.tags) if isinstance(self.tags, list) else self.tags,
                    actor_id=audit_actor_id,
                )
            )

        if logs:
            TaskAuditLog.objects.bulk_create(logs)


class TaskAuditLog(models.Model):
    """
    Append-only audit entries for Task changes.

    QuerySet.update() and other bulk writes bypass Model.save() and are not logged.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=32, choices=AuditAction.choices)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_audit_logs",
    )

    class Meta:
        ordering = ["created_at"]
