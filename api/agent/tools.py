from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from django.db import connection
from pydantic import BaseModel, Field, model_validator

from tasks.models import Task, TaskStatus
from tasks.services import UNSET, create_task, soft_delete_task, update_task


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
                        "description": "ISO 8601 datetime for when the task is due, e.g. 2026-04-10T09:00:00.",
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
                    "task_id": {"type": "integer", "description": "ID of the task to edit."},
                    "name": {"type": "string", "description": "New task title."},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "cancelled"],
                    },
                    "priority": {"type": "integer"},
                    "due_at": {
                        "type": "string",
                        "description": "ISO 8601 datetime. Use null or clear_due_at=true to remove it.",
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
                    "task_id": {"type": "integer", "description": "ID of the task to delete."},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Run a read-only SELECT query on the tasks_task table. "
                "The WHERE user_id = ? filter is added automatically — do not include it yourself. "
                "Example: SELECT id, name, status FROM tasks_task WHERE deleted_at IS NULL"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A SELECT SQL query on tasks_task.",
                    },
                },
                "required": ["query"],
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
    tags: list[str] = Field(default_factory=list)


class EditTaskArgs(BaseModel):
    task_id: int
    name: str | None = None
    status: TaskStatus | None = None
    priority: int | None = None
    due_at: str | None = None
    clear_due_at: bool = False
    tags: list[str] | None = None

    @model_validator(mode="after")
    def validate_due_at_inputs(self) -> "EditTaskArgs":
        if self.clear_due_at and self.due_at is not None:
            raise ValueError("Cannot set due_at and clear_due_at together.")
        return self


class DeleteTaskArgs(BaseModel):
    task_id: int


class RunSqlArgs(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _parse_due_at(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _tool_respond_to_user(args: RespondToUserArgs, user_id: int) -> str:
    return args.message


def _tool_create_task(args: CreateTaskArgs, user_id: int) -> str:
    due_at = _parse_due_at(args.due_at)
    task = create_task(
        user_id=user_id,
        name=args.name,
        status=args.status,
        priority=args.priority,
        due_at=due_at,
        tags=args.tags,
    )
    return json.dumps({"ok": True, "task_id": task.pk, "name": task.name})


def _tool_edit_task(args: EditTaskArgs, user_id: int) -> str:
    try:
        task = Task.objects.get(pk=args.task_id, user_id=user_id, deleted_at__isnull=True)
    except Task.DoesNotExist:
        return json.dumps({"ok": False, "error": f"Task {args.task_id} not found."})

    due_at = UNSET
    if "due_at" in args.model_fields_set:
        due_at = _parse_due_at(args.due_at)

    update_fields = update_task(
        task,
        audit_actor_id=user_id,
        name=args.name if args.name is not None else UNSET,
        status=args.status if args.status is not None else UNSET,
        priority=args.priority if args.priority is not None else UNSET,
        due_at=due_at,
        tags=args.tags if args.tags is not None else UNSET,
        clear_due_at=args.clear_due_at,
    )

    return json.dumps({"ok": True, "task_id": task.pk, "updated_fields": update_fields})


def _tool_delete_task(args: DeleteTaskArgs, user_id: int) -> str:
    try:
        task = Task.objects.get(pk=args.task_id, user_id=user_id, deleted_at__isnull=True)
    except Task.DoesNotExist:
        return json.dumps({"ok": False, "error": f"Task {args.task_id} not found."})

    soft_delete_task(task, audit_actor_id=user_id)
    return json.dumps({"ok": True, "task_id": args.task_id})


def _tool_run_sql(args: RunSqlArgs, user_id: int) -> str:
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
            if isinstance(v, datetime):
                row[k] = v.isoformat()

    return json.dumps({"ok": True, "rows": data, "count": len(data)})


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "respond_to_user": (RespondToUserArgs, _tool_respond_to_user),
    "create_task": (CreateTaskArgs, _tool_create_task),
    "edit_task": (EditTaskArgs, _tool_edit_task),
    "delete_task": (DeleteTaskArgs, _tool_delete_task),
    "run_sql": (RunSqlArgs, _tool_run_sql),
}


def execute_tool(tool_name: str, arguments: dict, user_id: int) -> str:
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
