from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from django.db.models import Q
from django.utils import timezone

from apps.tasks.models import Task


ToolHandler = Callable[..., dict[str, Any]]


def _task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "description": task.description,
        "status": task.status,
        "created_at": task.created_at.isoformat(),
        "due_at": task.due_at.isoformat() if task.due_at else None,
    }


def _parse_due_at(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, UTC)
    return parsed


def create_task(user_id: int, description: str, due_at: str | None = None) -> dict[str, Any]:
    try:
        task = Task.objects.create(
            user_id=user_id,
            description=description,
            due_at=_parse_due_at(due_at),
        )
        return {"ok": True, "data": _task_to_dict(task)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def list_tasks(
    user_id: int,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    try:
        if status:
            qs = Task.objects.filter(user_id=user_id, status=status)
        else:
            qs = Task.objects.filter(user_id=user_id)
        qs = qs.order_by("-created_at")[:limit]
        tasks = [_task_to_dict(task) for task in qs]
        return {"ok": True, "data": tasks, "count": len(tasks)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def search_tasks(
    user_id: int,
    query: str,
    status: str | None = "pending",
    limit: int = 10,
) -> dict[str, Any]:
    try:
        qs = Task.objects.filter(user_id=user_id)
        if status:
            qs = qs.filter(status=status)
        qs = qs.filter(Q(description__icontains=query)).order_by("-created_at")[:limit]
        tasks = [_task_to_dict(task) for task in qs]
        return {"ok": True, "data": tasks, "count": len(tasks)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def update_task(
    user_id: int,
    task_id: int,
    description: str | None = None,
    status: str | None = None,
    due_at: str | None = None,
) -> dict[str, Any]:
    try:
        task = Task.objects.get(id=task_id, user_id=user_id)
    except Task.DoesNotExist:
        return {"ok": False, "error": f"Task {task_id} not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    try:
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if due_at is not None:
            task.due_at = _parse_due_at(due_at)
        task.save()
        return {"ok": True, "data": _task_to_dict(task)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def complete_task(user_id: int, task_id: int) -> dict[str, Any]:
    return update_task(user_id, task_id=task_id, status=Task.Status.DONE)


def delete_task(user_id: int, task_id: int) -> dict[str, Any]:
    try:
        task = Task.objects.get(id=task_id, user_id=user_id)
        task.delete()
        return {"ok": True, "data": {"id": task_id}}
    except Task.DoesNotExist:
        return {"ok": False, "error": f"Task {task_id} not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler

    def as_llm_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def build_task_tools(user_id: int) -> list[RegisteredTool]:
    return [
        RegisteredTool(
            name="create_task",
            description="Create a task for the user.",
            input_schema={
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "due_at": {"type": "string", "description": "ISO datetime"},
                },
                "required": ["description"],
            },
            handler=lambda **kwargs: create_task(user_id, **kwargs),
        ),
        RegisteredTool(
            name="list_tasks",
            description="List the user's tasks.",
            input_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "done"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
            handler=lambda **kwargs: list_tasks(user_id, **kwargs),
        ),
        RegisteredTool(
            name="search_tasks",
            description="Search tasks by description.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "done"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
            handler=lambda **kwargs: search_tasks(user_id, **kwargs),
        ),
        RegisteredTool(
            name="update_task",
            description="Update a task's description, status, or due date.",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "done"]},
                    "due_at": {"type": "string", "description": "ISO datetime"},
                },
                "required": ["task_id"],
            },
            handler=lambda **kwargs: update_task(user_id, **kwargs),
        ),
        RegisteredTool(
            name="complete_task",
            description="Mark a task as done.",
            input_schema={
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
            handler=lambda **kwargs: complete_task(user_id, **kwargs),
        ),
        RegisteredTool(
            name="delete_task",
            description="Delete a task.",
            input_schema={
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
            handler=lambda **kwargs: delete_task(user_id, **kwargs),
        ),
    ]


RESPOND_TO_USER_DEFINITION: dict[str, Any] = {
    "name": "respond_to_user",
    "description": "Send the final user-facing message for this turn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
        },
        "required": ["message"],
    },
}


def summarize_tool_call(tool_name: str, tool_input: dict[str, Any], tool_output: dict[str, Any]) -> str:
    if not tool_output.get("ok"):
        return f"{tool_name} failed: {tool_output.get('error', 'unknown error')}"

    data = tool_output.get("data")
    if tool_name == "create_task" and data:
        return f'created task {data["id"]}: {data["description"][:40]}'
    if tool_name == "list_tasks":
        return f"listed tasks -> {tool_output.get('count', 0)} items"
    if tool_name == "search_tasks":
        return f'searched "{tool_input.get("query", "")}" -> {tool_output.get("count", 0)} items'
    if tool_name == "update_task" and data:
        return f'updated task {data["id"]}'
    if tool_name == "complete_task" and data:
        return f'completed task {data["id"]}'
    if tool_name == "delete_task" and data:
        return f'deleted task {data["id"]}'
    return f"{tool_name} ok"


def compact_tool_output(tool_name: str, output: dict[str, Any]) -> dict[str, Any]:
    if not output.get("ok"):
        return {"ok": False, "error": output.get("error", "unknown error")}

    data = output.get("data")
    if tool_name in {"list_tasks", "search_tasks"}:
        tasks = []
        for task in data or []:
            tasks.append(
                {
                    "id": task.get("id"),
                    "description": task.get("description"),
                    "status": task.get("status"),
                    "due_at": task.get("due_at"),
                }
            )
        return {"ok": True, "count": output.get("count", len(tasks)), "data": tasks}

    if tool_name in {"create_task", "update_task", "complete_task"} and isinstance(data, dict):
        return {
            "ok": True,
            "data": {
                "id": data.get("id"),
                "description": data.get("description"),
                "status": data.get("status"),
                "due_at": data.get("due_at"),
            },
        }

    if tool_name == "delete_task" and isinstance(data, dict):
        return {"ok": True, "data": {"id": data.get("id")}}

    return {"ok": True}
