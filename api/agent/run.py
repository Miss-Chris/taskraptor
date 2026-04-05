from __future__ import annotations

import json
from typing import Any

from typing import Callable

from agent.llm import (
    InactiveLlmModelError,
    MissingApiKeyError,
    QuotaExceededError,
    call_llm,
)
from agent.models import LlmModel
from agent.prompts import SYSTEM_PROMPT
from agent.schemas import (
    AgentResult,
    AssistantMessage,
    HistoryMessage,
    NewMessage,
    ToolCallFunction,
    ToolCallRecord,
    ToolResultMessage,
)
from agent.tools import TOOL_DEFINITIONS, execute_tool

MAX_ITERATIONS = 10
RESPOND_TO_USER_TOOL = "respond_to_user"


def run_agent(
    user_id: int,
    llm_model: LlmModel,
    history: list[HistoryMessage],
    new_message: str,
    llm_callable: Callable | None = None,
) -> AgentResult:
    """
    Run the agent loop.

    Builds a message list from the system prompt, prior history, and the new
    message, then repeatedly calls the LLM until it calls respond_to_user,
    produces no tool calls, or hits MAX_ITERATIONS.

    Returns a pure AgentResult -- no DB writes are performed here.
    Callers are responsible for persisting AgentRun / MessageLog records using
    AgentResult.new_messages, which contains every message emitted in order.

    ``llm_callable`` defaults to the real ``call_llm``; pass a scripted
    replacement in tests to avoid hitting the network.
    """
    _call = llm_callable if llm_callable is not None else call_llm

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *[m.to_api_dict() for m in history],
        {"role": "user", "content": new_message},
    ]

    new_messages: list[NewMessage] = [
        NewMessage(actor="user", content=new_message),
    ]

    all_tool_calls: list[ToolCallRecord] = []
    total_input_tokens = 0
    total_output_tokens = 0
    iterations = 0
    last_assistant_content = ""

    try:
        while iterations < MAX_ITERATIONS:
            iterations += 1

            response = _call(
                llm_model,
                messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )

            message = response.choices[0].message

            usage = getattr(response, "usage", None)
            if usage:
                total_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
                total_output_tokens += getattr(usage, "completion_tokens", 0) or 0

            if message.content:
                last_assistant_content = message.content

            tool_calls = message.tool_calls or []

            if not tool_calls:
                # LLM finished without calling any tool -- use text content as fallback
                break

            # Build a typed AssistantMessage for this turn and append to the thread.
            typed_assistant = AssistantMessage(
                content=message.content,
                tool_calls=[
                    ToolCallFunction(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                    for tc in tool_calls
                ],
            )
            messages.append(typed_assistant.to_api_dict())

            # Emit one tool_call NewMessage per tool call in this turn.
            # Store content so assistant thinking text survives the persistence round-trip.
            assistant_content = message.content or None
            for tc in tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                new_messages.append(
                    NewMessage(
                        actor="tool_call",
                        content=assistant_content,
                        tool_name=tc.function.name,
                        tool_call_id=tc.id,
                        arguments=arguments,
                    )
                )
                # Only carry content on the first tool_call in a multi-call turn.
                assistant_content = None

            final_response: str | None = None

            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                result = execute_tool(tool_name, arguments, user_id)

                all_tool_calls.append(
                    ToolCallRecord(
                        tool_name=tool_name,
                        tool_call_id=tc.id,
                        arguments=arguments,
                        result=result,
                    )
                )

                new_messages.append(
                    NewMessage(
                        actor="tool_result",
                        content=result,
                        tool_name=tool_name,
                        tool_call_id=tc.id,
                    )
                )

                typed_result = ToolResultMessage(
                    tool_call_id=tc.id,
                    name=tool_name,
                    content=result,
                )
                messages.append(typed_result.to_api_dict())

                if tool_name == RESPOND_TO_USER_TOOL:
                    try:
                        final_response = json.loads(result) if result.startswith("{") else result
                        if isinstance(final_response, dict):
                            final_response = arguments.get("message", result)
                    except Exception:
                        final_response = arguments.get("message", result)

            if final_response is not None:
                new_messages.append(
                    NewMessage(actor="assistant", content=final_response)
                )
                return AgentResult(
                    response_text=final_response,
                    new_messages=new_messages,
                    tool_calls=all_tool_calls,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    iterations=iterations,
                )

    except QuotaExceededError:
        fallback = "You've used up your message quota. Please upgrade or wait for it to reset."
        new_messages.append(NewMessage(actor="assistant", content=fallback))
        return AgentResult(
            response_text=fallback,
            new_messages=new_messages,
            tool_calls=all_tool_calls,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            error="quota_exceeded",
            iterations=iterations,
        )

    except (InactiveLlmModelError, MissingApiKeyError) as exc:
        fallback = "Your AI configuration needs attention. Please check your settings."
        new_messages.append(NewMessage(actor="assistant", content=fallback))
        return AgentResult(
            response_text=fallback,
            new_messages=new_messages,
            tool_calls=all_tool_calls,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            error=str(exc),
            iterations=iterations,
        )

    except Exception as exc:
        fallback = "Something went wrong. Please try again."
        new_messages.append(NewMessage(actor="assistant", content=fallback))
        return AgentResult(
            response_text=fallback,
            new_messages=new_messages,
            tool_calls=all_tool_calls,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            error=str(exc),
            iterations=iterations,
        )

    # Fallback: LLM ran out of iterations or produced no tool calls
    fallback_text = last_assistant_content or "I was unable to complete your request."
    new_messages.append(NewMessage(actor="assistant", content=fallback_text))
    return AgentResult(
        response_text=fallback_text,
        new_messages=new_messages,
        tool_calls=all_tool_calls,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        iterations=iterations,
    )
