from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def create_message(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> Any: ...


class AnthropicClient:
    def __init__(self, api_key: str) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)

    def create_message(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> Any:
        return self._client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools,  # type: ignore[arg-type]
            max_tokens=max_tokens,
        )
