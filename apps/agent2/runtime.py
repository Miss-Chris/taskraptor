from __future__ import annotations

import json
import zoneinfo
from datetime import datetime

from .llm import AnthropicClient, LLMClient
from .prompts import build_system_prompt
from .schemas import AgentAction, AgentRequest, AgentResponse, ToolCallResult
from .tools import (
    RESPOND_TO_USER_DEFINITION,
    RegisteredTool,
    compact_tool_output,
    summarize_tool_call,
)


def run_agent(
    request: AgentRequest,
    tools: list[RegisteredTool],
    llm_client: LLMClient | None = None,
) -> AgentResponse:
    if llm_client is None:
        llm_client = AnthropicClient(api_key=request.api_key)

    tool_map = {tool.name: tool for tool in tools}
    all_tools = [tool.as_llm_definition() for tool in tools] + [RESPOND_TO_USER_DEFINITION]

    try:
        tz = zoneinfo.ZoneInfo(request.user_timezone)
    except zoneinfo.ZoneInfoNotFoundError:
        tz = zoneinfo.ZoneInfo("UTC")

    system = build_system_prompt(
        timezone=request.user_timezone,
        current_time=datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z"),
        open_tasks=request.open_tasks,
    )
    messages: list[dict] = [
        {"role": entry.role, "content": entry.content}
        for entry in request.conversation_history
    ]
    messages.append({"role": "user", "content": request.message})

    actions: list[AgentAction] = []
    action_index = 0
    respond_call_count = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for _ in range(request.max_iterations):
        try:
            response = llm_client.create_message(
                model=request.model,
                system=system,
                messages=messages,
                tools=all_tools,
                max_tokens=request.llm_max_tokens,
            )
        except Exception as exc:
            return AgentResponse(
                actions=actions,
                stopped_reason="error",
                error=str(exc),
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        usage = getattr(response, "usage", None)
        if usage:
            total_input_tokens += getattr(usage, "input_tokens", 0)
            total_output_tokens += getattr(usage, "output_tokens", 0)

        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_use_blocks = [block for block in assistant_content if block.type == "tool_use"]
        if not tool_use_blocks:
            return AgentResponse(
                actions=actions,
                stopped_reason="completed",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        tool_results: list[dict] = []
        reached_respond_limit = False

        for block in tool_use_blocks:
            tool_name = block.name
            tool_input = block.input

            if tool_name == "respond_to_user":
                respond_call_count += 1
                message_text = tool_input.get("message", "")
                actions.append(
                    AgentAction(
                        index=action_index,
                        type="user_message",
                        user_message=message_text,
                    )
                )
                action_index += 1
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": '{"ok": true}',
                    }
                )
                if respond_call_count >= request.max_respond_calls:
                    reached_respond_limit = True
                    break
                continue

            tool = tool_map.get(tool_name)
            if tool is None:
                output: dict[str, object] = {"ok": False, "error": f"Unknown tool: {tool_name}"}
            else:
                try:
                    output = tool.handler(**tool_input)
                except Exception as exc:
                    output = {"ok": False, "error": str(exc)}

            actions.append(
                AgentAction(
                    index=action_index,
                    type="tool_call",
                    tool_call=ToolCallResult(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_output=output,
                        summary=summarize_tool_call(tool_name, tool_input, output),
                    ),
                )
            )
            action_index += 1
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(compact_tool_output(tool_name, output)),
                }
            )

        messages.append({"role": "user", "content": tool_results})

        if reached_respond_limit:
            return AgentResponse(
                actions=actions,
                stopped_reason="max_respond_calls",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

    return AgentResponse(
        actions=actions,
        stopped_reason="max_iterations",
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
    )

