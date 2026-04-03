from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConversationEntry(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class TaskContextEntry(BaseModel):
    id: int
    description: str
    status: Literal["pending", "done"]
    due_at: str | None


class AgentRequest(BaseModel):
    api_key: str
    user_id: int
    user_timezone: str
    message: str
    conversation_history: list[ConversationEntry] = Field(default_factory=list)
    open_tasks: list[TaskContextEntry] = Field(default_factory=list)
    model: str = "claude-sonnet-4-5"
    max_iterations: int = 12
    max_respond_calls: int = 2
    llm_max_tokens: int = 1024


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
    actions: list[AgentAction]
    stopped_reason: Literal["completed", "max_iterations", "max_respond_calls", "error"]
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class AgentTokenEstimate(BaseModel):
    initial_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    method: Literal["anthropic_count_tokens", "heuristic"]
