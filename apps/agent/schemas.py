from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationEntry(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ToolCallEntry(BaseModel):
    index: int
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: dict[str, Any]
    summary: str


class TodoSchema(BaseModel):
    id: str
    title: str
    notes: str
    priority: Literal["low", "medium", "high"]
    tags: list[str]
    is_completed: bool
    due_date: str | None
    due_time: str | None
    alarm_at: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class ScheduleSchema(BaseModel):
    id: str
    instruction: str
    cron_expression: str
    is_recurring: bool
    is_active: bool
    next_run_at: str


class ToolContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    add_todo: Callable[..., dict]
    list_todos: Callable[..., dict]
    update_todo: Callable[..., dict]
    delete_todo: Callable[..., dict]
    search_todos: Callable[..., dict]
    create_schedule: Callable[..., dict]
    list_schedules: Callable[..., dict]
    delete_schedule: Callable[..., dict]


class AgentRequest(BaseModel):
    api_key: str
    user_id: int
    user_timezone: str
    message: str
    conversation_history: list[ConversationEntry] = Field(default_factory=list)
    tool_call_history: list[ToolCallEntry] = Field(default_factory=list)
    model: str = "claude-sonnet-4-5"
    max_iterations: int = 15
    max_respond_calls: int = 3


class ToolCallResult(BaseModel):
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: dict[str, Any]
    summary: str


class AgentAction(BaseModel):
    index: int
    type: Literal["tool_call", "user_message"]
    tool_call: ToolCallResult | None = None
    user_message: str | None = None


class AgentResponse(BaseModel):
    agent_run_id: str | None = None
    actions: list[AgentAction]
    stopped_reason: Literal["completed", "max_iterations", "max_respond_calls", "error"]
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
