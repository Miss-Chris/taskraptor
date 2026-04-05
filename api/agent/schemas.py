from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Typed history message models (one per litellm role)
# ---------------------------------------------------------------------------

class ToolCallFunction(BaseModel):
    """A single tool call as returned by the LLM."""

    id: str
    name: str
    arguments: str  # raw JSON string, as litellm returns


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str

    def to_api_dict(self) -> dict[str, Any]:
        return {"role": "user", "content": self.content}


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ToolCallFunction] = Field(default_factory=list)

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in self.tool_calls
            ]
        return d


class ToolResultMessage(BaseModel):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str
    content: str

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "content": self.content,
        }


HistoryMessage = Annotated[
    UserMessage | AssistantMessage | ToolResultMessage,
    Field(discriminator="role"),
]


# ---------------------------------------------------------------------------
# Agent run schemas
# ---------------------------------------------------------------------------

class ToolCallRecord(BaseModel):
    tool_name: str
    tool_call_id: str
    arguments: dict
    result: str


class NewMessage(BaseModel):
    """
    A single message produced during an agent run, in the order it was emitted.

    Callers persist these as MessageLog rows. The sequence is designed to round-trip
    cleanly through history_from_message_logs(): tool_call entries that share an LLM
    turn appear consecutively, followed by their matching tool_result entries.
    """

    actor: str  # "user" | "assistant" | "tool_call" | "tool_result"
    content: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    arguments: dict | None = None


class AgentResult(BaseModel):
    response_text: str
    new_messages: list[NewMessage] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    iterations: int = 0
