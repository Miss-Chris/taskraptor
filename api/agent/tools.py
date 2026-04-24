from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import connection
from django.utils import timezone
from pydantic import BaseModel, Field, model_validator

from accounts.models import User
from tasks.models import DueType, Task, TaskStatus
from tasks.services import UNSET, create_task, soft_delete_task, update_task
from taskraptor.timezones import parse_user_datetime, serialize_datetime_with_local


# ---------------------------------------------------------------------------
# Tool definitions (litellm / OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "respond_to_user",
            "description": (
                "Send the final reply to the user. MUST be called at the end of every response."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to send to the user.",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task for the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Task title."},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "cancelled"],
                        "description": "Initial status (default: pending).",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority level; higher = more important (default: 0).",
                    },
                    "due_at": {
                        "type": "string",
                        "description": "ISO 8601 local date or datetime for when the task is due. Date-only values are due at the end of that local day. The backend normalizes to UTC using the user's timezone.",
                    },
                    "due_type": {
                        "type": "string",
                        "enum": ["date", "time"],
                        "description": "Use date for date-only due dates and time for due dates with an explicit time.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tag strings.",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_task",
            "description": "Update one or more fields on an existing task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the task to edit.",
                    },
                    "name": {"type": "string", "description": "New task title."},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "cancelled"],
                    },
                    "priority": {"type": "integer"},
                    "due_at": {
                        "type": "string",
                        "description": "ISO 8601 local date or datetime. Use null or clear_due_at=true to remove it. The backend normalizes to UTC using the user's timezone.",
                    },
                    "due_type": {
                        "type": "string",
                        "enum": ["date", "time"],
                    },
                    "clear_due_at": {
                        "type": "boolean",
                        "description": "Set true to clear the due date.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Soft-delete a task. The task is not permanently removed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the task to delete.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_tasks",
            "description": (
                "Search and list the user's active tasks. Use this before editing or deleting "
                "when you need to find a task ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "cancelled"],
                        "description": "Filter by task status.",
                    },
                    "tag": {
                        "type": "string",
                        "description": "Filter to tasks containing this tag.",
                    },
                    "upcoming": {
                        "type": "boolean",
                        "description": "Only tasks with a future due date, excluding completed tasks.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Filter by exact priority.",
                    },
                    "min_priority": {
                        "type": "integer",
                        "description": "Filter to tasks with priority greater than or equal to this value.",
                    },
                    "max_priority": {
                        "type": "integer",
                        "description": "Filter to tasks with priority less than or equal to this value.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Case-insensitive text search within task names.",
                    },
                    "include_completed": {
                        "type": "boolean",
                        "description": "Whether completed tasks should be included. Defaults to true.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return. Capped at 100.",
                    },
                },
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Pydantic argument models for validation
# ---------------------------------------------------------------------------

class RespondToUserArgs(BaseModel):
    message: str


class CreateTaskArgs(BaseModel):
    name: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    due_at: str | None = None
    due_type: DueType | None = None
    tags: list[str] = Field(default_factory=list)


class EditTaskArgs(BaseModel):
    task_id: UUID
    name: str | None = None
    status: TaskStatus | None = None
    priority: int | None = None
    due_at: str | None = None
    due_type: DueType | None = None
    clear_due_at: bool = False
    tags: list[str] | None = None

    @model_validator(mode="after")
    def validate_due_at_inputs(self) -> "EditTaskArgs":
        if self.clear_due_at and self.due_at is not None:
            raise ValueError("Cannot set due_at and clear_due_at together.")
        return self


class DeleteTaskArgs(BaseModel):
    task_id: UUID


class QueryTasksArgs(BaseModel):
    status: TaskStatus | None = None
    tag: str | None = None
    upcoming: bool = False
    priority: int | None = None
    min_priority: int | None = None
    max_priority: int | None = None
    search: str | None = None
    include_completed: bool = True
    limit: int = 100


class RunSqlArgs(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _parse_due_at(value: str | None, user_timezone: str) -> tuple[datetime | None, DueType | None]:
    due_at, is_date_only = parse_user_datetime(value, user_timezone)
    if value is None:
        return due_at, None
    return due_at, DueType.DATE if is_date_only else DueType.TIME


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, UUID)):
        return str(value) if isinstance(value, UUID) else value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _tool_respond_to_user(args: RespondToUserArgs, user_id: UUID) -> str:
    return args.message


def _tool_create_task(args: CreateTaskArgs, user_id: UUID) -> str:
    user = User.objects.get(pk=user_id)
    due_at, inferred_due_type = _parse_due_at(args.due_at, user.timezone)
    task = create_task(
        user_id=user_id,
        name=args.name,
        status=args.status,
        priority=args.priority,
        due_at=due_at,
        due_type=args.due_type or inferred_due_type or DueType.TIME,
        tags=args.tags,
    )
    return json.dumps({"ok": True, "task_id": str(task.pk), "name": task.name})


def _tool_edit_task(args: EditTaskArgs, user_id: UUID) -> str:
    try:
        task = Task.objects.get(pk=args.task_id, user_id=user_id, deleted_at__isnull=True)
    except Task.DoesNotExist:
        return json.dumps({"ok": False, "error": f"Task {args.task_id} not found."})

    user = User.objects.get(pk=user_id)
    due_at = UNSET
    due_type = UNSET
    if "due_at" in args.model_fields_set:
        due_at, inferred_due_type = _parse_due_at(args.due_at, user.timezone)
        if args.due_at is not None:
            due_type = args.due_type or inferred_due_type or DueType.TIME
        elif args.due_type is not None:
            due_type = args.due_type
    elif args.due_type is not None:
        due_type = args.due_type

    update_fields = update_task(
        task,
        audit_actor_id=user_id,
        name=args.name if args.name is not None else UNSET,
        status=args.status if args.status is not None else UNSET,
        priority=args.priority if args.priority is not None else UNSET,
        due_at=due_at,
        due_type=due_type,
        tags=args.tags if args.tags is not None else UNSET,
        clear_due_at=args.clear_due_at,
    )

    return json.dumps({"ok": True, "task_id": str(task.pk), "updated_fields": update_fields})


def _tool_delete_task(args: DeleteTaskArgs, user_id: UUID) -> str:
    try:
        task = Task.objects.get(pk=args.task_id, user_id=user_id, deleted_at__isnull=True)
    except Task.DoesNotExist:
        return json.dumps({"ok": False, "error": f"Task {args.task_id} not found."})

    soft_delete_task(task, audit_actor_id=user_id)
    return json.dumps({"ok": True, "task_id": str(args.task_id)})


def _task_to_dict(task: Task, user_timezone: str) -> dict[str, Any]:
    tags = task.tags if isinstance(task.tags, list) else []
    due_at = serialize_datetime_with_local(task.due_at, user_timezone)
    return {
        "id": str(task.pk),
        "name": task.name,
        "status": task.status,
        "priority": task.priority,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "due_at_local": due_at["local"],
        "due_date_local": due_at["local_date"],
        "due_type": task.due_type,
        "timezone": due_at["timezone"],
        "tags": [str(tag) for tag in tags],
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "archived_at": task.archived_at.isoformat() if task.archived_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def _tool_query_tasks(args: QueryTasksArgs, user_id: UUID) -> str:
    user = User.objects.get(pk=user_id)
    qs = Task.objects.filter(user_id=user_id, deleted_at__isnull=True)

    if args.status is not None:
        qs = qs.filter(status=args.status)

    if args.include_completed is False:
        qs = qs.exclude(status=TaskStatus.COMPLETED)

    if args.upcoming:
        qs = qs.filter(due_at__isnull=False, due_at__gte=timezone.now()).exclude(
            status=TaskStatus.COMPLETED
        )

    if args.priority is not None:
        qs = qs.filter(priority=args.priority)
    else:
        if args.min_priority is not None:
            qs = qs.filter(priority__gte=args.min_priority)
        if args.max_priority is not None:
            qs = qs.filter(priority__lte=args.max_priority)

    if args.search is not None and args.search.strip():
        qs = qs.filter(name__icontains=args.search.strip())

    if args.tag is not None and args.tag.strip():
        tag = args.tag.strip()
        connection_features = connection.features
        if connection_features.supports_json_field_contains:
            qs = qs.filter(tags__contains=[tag])
        else:
            match_ids: list[UUID] = [
                pk
                for pk, tag_list in qs.values_list("pk", "tags")
                if isinstance(tag_list, list) and tag in (str(x) for x in tag_list)
            ]
            qs = qs.filter(pk__in=match_ids)

    limit = max(0, min(args.limit, 100))
    tasks = list(qs[:limit])
    return json.dumps(
        {
            "ok": True,
            "tasks": [_task_to_dict(task, user.timezone) for task in tasks],
            "count": len(tasks),
        },
        default=_json_default,
    )


# Raw SQL is intentionally retained for future/dev use but is not exposed in
# TOOL_DEFINITIONS or _TOOL_MAP. Do not wire this into the agent by default.
def _tool_run_sql(args: RunSqlArgs, user_id: UUID) -> str:
    query = args.query.strip()

    if not query.upper().startswith("SELECT"):
        return json.dumps({"ok": False, "error": "Only SELECT queries are allowed."})

    # Enforce user scope via a CTE so the LLM never sees another user's data.
    # The LLM is told to write queries against tasks_task; we silently replace
    # that with a pre-filtered alias.
    safe_query = f"""
        WITH _scoped AS (
            SELECT * FROM tasks_task WHERE user_id = %s
        )
        SELECT _q.* FROM ({query.replace("tasks_task", "_scoped")}) AS _q
    """

    with connection.cursor() as cursor:
        cursor.execute(safe_query, [user_id])
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchmany(100)  # cap at 100 rows

    data = [dict(zip(columns, row)) for row in rows]
    # Convert non-serializable types (datetime, etc.)
    for row in data:
        for k, v in row.items():
            if isinstance(v, (datetime, UUID)):
                row[k] = _json_default(v)

    return json.dumps({"ok": True, "rows": data, "count": len(data)}, default=_json_default)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "respond_to_user": (RespondToUserArgs, _tool_respond_to_user),
    "create_task": (CreateTaskArgs, _tool_create_task),
    "edit_task": (EditTaskArgs, _tool_edit_task),
    "delete_task": (DeleteTaskArgs, _tool_delete_task),
    "query_tasks": (QueryTasksArgs, _tool_query_tasks),
}


def execute_tool(tool_name: str, arguments: dict, user_id: UUID) -> str:
    """
    Validate and execute a tool call. Always returns a string (JSON or plain text)
    suitable for feeding back to the LLM as a tool result.

    Never raises -- errors are returned as JSON so the LLM can recover.
    """
    entry = _TOOL_MAP.get(tool_name)
    if entry is None:
        return json.dumps({"ok": False, "error": f"Unknown tool: {tool_name}"})

    args_model, handler = entry
    try:
        args = args_model.model_validate(arguments)
        return handler(args, user_id)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
