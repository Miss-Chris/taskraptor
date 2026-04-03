from __future__ import annotations

import json
import zoneinfo
from datetime import datetime

from .llm import AnthropicClient, LLMClient
from .prompts import build_system_prompt
from .schemas import AgentAction, AgentRequest, AgentResponse, ToolCallResult, ToolContext
from .tools import RESPOND_TO_USER_DEFINITION, TOOL_DEFINITIONS, summarize_tool_call


def run_agent(
    request: AgentRequest,
    tool_context: ToolContext,
    llm_client: LLMClient | None = None,
) -> AgentResponse:
    if llm_client is None:
        llm_client = AnthropicClient(api_key=request.api_key)

    # Build system prompt
    try:
        tz = zoneinfo.ZoneInfo(request.user_timezone)
    except zoneinfo.ZoneInfoNotFoundError:
        tz = zoneinfo.ZoneInfo("UTC")

    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")
    tool_history_str = _format_tool_history(request.tool_call_history)
    system = build_system_prompt(
        timezone=request.user_timezone,
        current_time=current_time,
        tool_call_history=tool_history_str,
        max_respond_calls=request.max_respond_calls,
    )

    # Build initial messages
    messages: list[dict] = [
        {"role": e.role, "content": e.content}
        for e in request.conversation_history
    ]
    messages.append({"role": "user", "content": request.message})

    all_tools = TOOL_DEFINITIONS + [RESPOND_TO_USER_DEFINITION]
    actions: list[AgentAction] = []
    respond_call_count = 0
    action_index = 0
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
        except Exception as e:
            return AgentResponse(
                actions=actions,
                stopped_reason="error",
                error=str(e),
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        usage = getattr(response, "usage", None)
        if usage:
            total_input_tokens += getattr(usage, "input_tokens", 0)
            total_output_tokens += getattr(usage, "output_tokens", 0)

        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_use_blocks = [b for b in assistant_content if b.type == "tool_use"]

        if not tool_use_blocks:
            # Model produced end_turn with no tool calls
            return AgentResponse(
                actions=actions,
                stopped_reason="completed",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

        tool_results = []
        reached_respond_limit = False

        for block in tool_use_blocks:
            tool_name: str = block.name
            tool_input: dict = block.input

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

            # Real tool dispatch
            tool_fn = getattr(tool_context, tool_name, None)
            if tool_fn is None:
                output: dict = {"ok": False, "error": f"Unknown tool: {tool_name}"}
            else:
                try:
                    output = tool_fn(**tool_input)
                except Exception as e:
                    output = {"ok": False, "error": str(e)}

            summary = summarize_tool_call(tool_name, tool_input, output)
            actions.append(
                AgentAction(
                    index=action_index,
                    type="tool_call",
                    tool_call=ToolCallResult(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_output=output,
                        summary=summary,
                    ),
                )
            )
            action_index += 1
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(_compact_tool_output(tool_name, output)),
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


def _format_tool_history(entries) -> str:
    if not entries:
        return ""
    lines = []
    for e in entries:
        lines.append(f"  [{e.index}] {e.tool_name}: {e.summary}")
    return "\n".join(lines)


def _compact_tool_output(tool_name: str, output: dict) -> dict:
    if not output.get("ok"):
        return {"ok": False, "error": output.get("error", "unknown error")}

    data = output.get("data")
    if tool_name in {"list_todos", "search_todos"}:
        todos = []
        for todo in data or []:
            todos.append(
                {
                    "id": todo.get("id"),
                    "title": todo.get("title"),
                    "priority": todo.get("priority"),
                    "is_completed": todo.get("is_completed"),
                    "due_date": todo.get("due_date"),
                }
            )
        return {"ok": True, "count": output.get("count", len(todos)), "data": todos}

    if tool_name in {"add_todo", "update_todo"} and isinstance(data, dict):
        return {
            "ok": True,
            "data": {
                "id": data.get("id"),
                "title": data.get("title"),
                "priority": data.get("priority"),
                "is_completed": data.get("is_completed"),
                "due_date": data.get("due_date"),
            },
        }

    if tool_name == "create_schedule" and isinstance(data, dict):
        return {
            "ok": True,
            "data": {
                "id": data.get("id"),
                "instruction": data.get("instruction"),
                "is_recurring": data.get("is_recurring"),
                "next_run_at": data.get("next_run_at"),
            },
        }

    if tool_name == "list_schedules":
        schedules = []
        for schedule in data or []:
            schedules.append(
                {
                    "id": schedule.get("id"),
                    "instruction": schedule.get("instruction"),
                    "next_run_at": schedule.get("next_run_at"),
                }
            )
        return {"ok": True, "count": output.get("count", len(schedules)), "data": schedules}

    if tool_name in {"delete_todo", "delete_schedule"} and isinstance(data, dict):
        return {"ok": True, "data": {"id": data.get("id")}}

    return {"ok": True}
