from __future__ import annotations

from typing import Any


def _todo_to_dict(todo) -> dict[str, Any]:
    return {
        "id": str(todo.id),
        "title": todo.title,
        "notes": todo.notes,
        "priority": todo.priority,
        "tags": todo.tags,
        "is_completed": todo.is_completed,
        "due_date": todo.due_date.isoformat() if todo.due_date else None,
        "due_time": todo.due_time.isoformat() if todo.due_time else None,
        "alarm_at": todo.alarm_at.isoformat() if todo.alarm_at else None,
        "created_at": todo.created_at.isoformat(),
        "updated_at": todo.updated_at.isoformat(),
        "completed_at": todo.completed_at.isoformat() if todo.completed_at else None,
    }


def _schedule_to_dict(schedule) -> dict[str, Any]:
    return {
        "id": str(schedule.id),
        "instruction": schedule.instruction,
        "cron_expression": schedule.cron_expression,
        "is_recurring": schedule.is_recurring,
        "is_active": schedule.is_active,
        "next_run_at": schedule.next_run_at.isoformat(),
    }


def add_todo(
    user_id: int,
    title: str,
    notes: str = "",
    priority: str = "medium",
    tags: list[str] | None = None,
    due_date: str | None = None,
    due_time: str | None = None,
    alarm_at: str | None = None,
) -> dict[str, Any]:
    from datetime import date, datetime, time

    from .models import Todo

    try:
        todo = Todo(
            user_id=user_id,
            title=title,
            notes=notes,
            priority=priority,
            tags=tags or [],
        )
        if due_date:
            todo.due_date = date.fromisoformat(due_date)
        if due_time:
            todo.due_time = time.fromisoformat(due_time)
        if alarm_at:
            todo.alarm_at = datetime.fromisoformat(alarm_at)
        todo.save()
        return {"ok": True, "data": _todo_to_dict(todo)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_todos(
    user_id: int,
    include_completed: bool = False,
    priority: str | None = None,
) -> dict[str, Any]:
    from .models import Todo

    try:
        qs = Todo.objects.filter(user_id=user_id)
        if not include_completed:
            qs = qs.filter(is_completed=False)
        if priority:
            qs = qs.filter(priority=priority)
        todos = [_todo_to_dict(t) for t in qs]
        return {"ok": True, "data": todos, "count": len(todos)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_todo(user_id: int, todo_id: str, **fields) -> dict[str, Any]:
    from datetime import date, datetime, time

    from django.utils import timezone

    from .models import Todo

    try:
        todo = Todo.objects.get(id=todo_id, user_id=user_id)
    except Todo.DoesNotExist:
        return {"ok": False, "error": f"Todo {todo_id} not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        allowed = {"title", "notes", "priority", "tags", "is_completed", "due_date", "due_time", "alarm_at"}
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "due_date":
                value = date.fromisoformat(value) if value else None
            elif key == "due_time":
                value = time.fromisoformat(value) if value else None
            elif key == "alarm_at":
                value = datetime.fromisoformat(value) if value else None
            elif key == "is_completed" and value and not todo.is_completed:
                todo.completed_at = timezone.now()
            setattr(todo, key, value)
        todo.save()
        return {"ok": True, "data": _todo_to_dict(todo)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete_todo(user_id: int, todo_id: str) -> dict[str, Any]:
    from .models import Todo

    try:
        todo = Todo.objects.get(id=todo_id, user_id=user_id)
        todo.delete()
        return {"ok": True, "data": {"id": todo_id}}
    except Todo.DoesNotExist:
        return {"ok": False, "error": f"Todo {todo_id} not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def search_todos(user_id: int, query: str) -> dict[str, Any]:
    from django.db.models import Q

    from .models import Todo

    try:
        qs = Todo.objects.filter(
            user_id=user_id, is_completed=False
        ).filter(Q(title__icontains=query) | Q(notes__icontains=query))
        todos = [_todo_to_dict(t) for t in qs]
        return {"ok": True, "data": todos, "count": len(todos)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def create_schedule(
    user_id: int,
    instruction: str,
    cron_expression: str,
    is_recurring: bool = True,
    next_run_at: str | None = None,
) -> dict[str, Any]:
    from datetime import timedelta

    from django.utils import timezone

    from .models import Schedule

    try:
        if next_run_at:
            from datetime import datetime
            run_at = datetime.fromisoformat(next_run_at)
        else:
            run_at = timezone.now() + timedelta(minutes=1)

        schedule = Schedule.objects.create(
            user_id=user_id,
            instruction=instruction,
            cron_expression=cron_expression,
            is_recurring=is_recurring,
            next_run_at=run_at,
        )
        return {"ok": True, "data": _schedule_to_dict(schedule)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_schedules(user_id: int) -> dict[str, Any]:
    from .models import Schedule

    try:
        schedules = [_schedule_to_dict(s) for s in Schedule.objects.filter(user_id=user_id, is_active=True)]
        return {"ok": True, "data": schedules, "count": len(schedules)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete_schedule(user_id: int, schedule_id: str) -> dict[str, Any]:
    from .models import Schedule

    try:
        schedule = Schedule.objects.get(id=schedule_id, user_id=user_id)
        schedule.delete()
        return {"ok": True, "data": {"id": schedule_id}}
    except Schedule.DoesNotExist:
        return {"ok": False, "error": f"Schedule {schedule_id} not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def summarize_tool_call(tool_name: str, tool_input: dict, tool_output: dict) -> str:
    if not tool_output.get("ok"):
        return f"{tool_name} failed: {tool_output.get('error', 'unknown error')}"

    data = tool_output.get("data")
    if tool_name == "add_todo" and data:
        due = f", due:{data['due_date']}" if data.get("due_date") else ""
        return f'added "{data["title"]}" (id:{data["id"][:8]}{due})'
    elif tool_name == "list_todos":
        return f"listed todos → {tool_output.get('count', 0)} items"
    elif tool_name == "update_todo" and data:
        return f"updated {data['id'][:8]}"
    elif tool_name == "delete_todo" and data:
        return f"deleted {data['id'][:8]}"
    elif tool_name == "search_todos":
        q = tool_input.get("query", "")
        return f'searched "{q}" → {tool_output.get("count", 0)} items'
    elif tool_name == "create_schedule" and data:
        return f'scheduled "{data["instruction"][:40]}"'
    elif tool_name == "list_schedules":
        return f"listed schedules → {tool_output.get('count', 0)} items"
    elif tool_name == "delete_schedule" and data:
        return f"deleted schedule {data['id'][:8]}"
    return f"{tool_name} ok"


TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "add_todo",
        "description": "Create a new todo item for the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "The todo title"},
                "notes": {"type": "string", "description": "Optional additional notes"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Priority level",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags",
                },
                "due_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD in user's local timezone",
                },
                "due_time": {
                    "type": "string",
                    "description": "Time HH:MM in user's local timezone",
                },
                "alarm_at": {
                    "type": "string",
                    "description": "ISO datetime UTC for an alarm",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_todos",
        "description": "List the user's todos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_completed": {
                    "type": "boolean",
                    "description": "Include completed todos (default false)",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Filter by priority",
                },
            },
        },
    },
    {
        "name": "update_todo",
        "description": "Update fields on an existing todo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "The todo UUID"},
                "title": {"type": "string"},
                "notes": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "tags": {"type": "array", "items": {"type": "string"}},
                "is_completed": {"type": "boolean"},
                "due_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "due_time": {"type": "string", "description": "HH:MM"},
                "alarm_at": {"type": "string", "description": "ISO datetime UTC"},
            },
            "required": ["todo_id"],
        },
    },
    {
        "name": "delete_todo",
        "description": "Delete a todo by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "The todo UUID"},
            },
            "required": ["todo_id"],
        },
    },
    {
        "name": "search_todos",
        "description": "Search todos by keyword in title or notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_schedule",
        "description": "Create a scheduled agent run (recurring or one-shot).",
        "input_schema": {
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "What the agent should do when triggered",
                },
                "cron_expression": {
                    "type": "string",
                    "description": "5-field cron expression (e.g. '0 9 * * *' for 9am daily). Leave blank for one-shot.",
                },
                "is_recurring": {
                    "type": "boolean",
                    "description": "Whether this repeats on the cron schedule",
                },
                "next_run_at": {
                    "type": "string",
                    "description": "ISO datetime UTC for the first run",
                },
            },
            "required": ["instruction"],
        },
    },
    {
        "name": "list_schedules",
        "description": "List the user's active schedules.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "delete_schedule",
        "description": "Delete a schedule by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "schedule_id": {"type": "string", "description": "The schedule UUID"},
            },
            "required": ["schedule_id"],
        },
    },
]

RESPOND_TO_USER_DEFINITION: dict = {
    "name": "respond_to_user",
    "description": (
        "Send a message to the user. Always use this tool to communicate — "
        "never produce text outside of tool calls."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The message to send"},
        },
        "required": ["message"],
    },
}
