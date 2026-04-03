from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeContentBlock:
    type: str
    id: str = "fake_tool_use_id"
    name: str = ""
    input: dict = field(default_factory=dict)
    text: str = ""


@dataclass
class FakeMessage:
    content: list[FakeContentBlock]
    stop_reason: str = "tool_use"


def tool_use_block(name: str, input: dict, id: str = "fake_id") -> FakeContentBlock:
    return FakeContentBlock(type="tool_use", name=name, input=input, id=id)


def end_turn_block(text: str = "") -> FakeContentBlock:
    return FakeContentBlock(type="text", text=text)


def respond_block(message: str, id: str = "respond_id") -> FakeContentBlock:
    return FakeContentBlock(
        type="tool_use", name="respond_to_user", input={"message": message}, id=id
    )


class FakeLLMClient:
    def __init__(self, responses: list[FakeMessage]) -> None:
        self._responses = list(responses)
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    def create_message(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> FakeMessage:
        self.call_count += 1
        self.calls.append(
            {
                "model": model,
                "system": system,
                "messages": copy.deepcopy(messages),
                "tools": copy.deepcopy(tools),
                "max_tokens": max_tokens,
            }
        )
        if not self._responses:
            return FakeMessage(content=[end_turn_block()])
        return self._responses.pop(0)
