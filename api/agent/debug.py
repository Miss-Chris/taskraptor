from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from django.db.models import Count, Max, OuterRef, Subquery

from accounts.models import User
from agent.models import AgentRun, LlmModel, MessageLog
from automations.models import Automation
from channels.models import Channel, Conversation, WebChatMessage
from tasks.models import Task, TaskAuditLog

REDACTED = "[redacted]"


def _serialize(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return value


def _model_summary(model: LlmModel) -> dict[str, Any]:
    return {
        "id": str(model.pk),
        "model_key": model.model_key,
        "api_key": REDACTED if model.api_key else "",
        "has_api_key": bool(model.api_key),
        "quota": model.quota,
        "quota_used": model.quota_used,
        "quota_expires_at": _serialize(model.quota_expires_at),
        "context_message_limit": model.context_message_limit,
        "is_active": model.is_active,
        "created_at": _serialize(model.created_at),
        "updated_at": _serialize(model.updated_at),
    }


def user_debug_summary(user: User, *, limit: int = 10) -> dict[str, Any]:
    conversations = Conversation.objects.filter(channel__user=user)
    runs = AgentRun.objects.filter(user=user)
    recent_runs = [
        {
            "id": str(run.pk),
            "conversation_id": str(run.conversation_id),
            "channel_id": str(run.channel_id),
            "status": run.status,
            "model_key": run.llm_model.model_key,
            "error": run.error,
            "created_at": _serialize(run.created_at),
            "started_at": _serialize(run.started_at),
            "completed_at": _serialize(run.completed_at),
        }
        for run in runs.select_related("llm_model").order_by("-created_at")[:limit]
    ]
    return {
        "user": _user_summary(user),
        "counts": {
            "channels": Channel.objects.filter(user=user).count(),
            "conversations": conversations.count(),
            "agent_runs": runs.count(),
            "failed_agent_runs": runs.filter(status="failed").count(),
            "message_logs": MessageLog.objects.filter(conversation__channel__user=user).count(),
            "visible_web_messages": WebChatMessage.objects.filter(
                conversation__channel__user=user
            ).count(),
            "tasks": Task.objects.filter(user=user, deleted_at__isnull=True).count(),
            "automations": Automation.objects.filter(user=user, is_active=True).count(),
        },
        "recent_runs": recent_runs,
        "llm_models": [
            _model_summary(model)
            for model in LlmModel.objects.filter(user=user).order_by("-created_at")
        ],
    }


def list_debug_conversations(user: User, *, limit: int = 50) -> list[dict[str, Any]]:
    latest_message_content = WebChatMessage.objects.filter(
        conversation=OuterRef("pk")
    ).order_by("-created_at").values("content")[:1]
    latest_message_role = WebChatMessage.objects.filter(
        conversation=OuterRef("pk")
    ).order_by("-created_at").values("role")[:1]
    latest_run_status = AgentRun.objects.filter(
        conversation=OuterRef("pk")
    ).order_by("-created_at").values("status")[:1]

    qs = (
        Conversation.objects.filter(channel__user=user)
        .select_related("channel")
        .annotate(
            run_count=Count("agent_runs", distinct=True),
            message_log_count=Count("agent_message_logs", distinct=True),
            visible_message_count=Count("web_messages", distinct=True),
            latest_run_at=Max("agent_runs__created_at"),
            latest_visible_message=Subquery(latest_message_content),
            latest_visible_role=Subquery(latest_message_role),
            latest_run_status=Subquery(latest_run_status),
        )
        .order_by("-updated_at", "-created_at")[:limit]
    )
    return [_conversation_list_item(conversation) for conversation in qs]


def conversation_debug_bundle(
    user: User,
    conversation_id: UUID,
    *,
    run_id: UUID | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    conversation = Conversation.objects.select_related("channel").get(
        pk=conversation_id,
        channel__user=user,
    )
    runs_qs = AgentRun.objects.filter(conversation=conversation, user=user)
    if run_id is not None:
        runs_qs = runs_qs.filter(pk=run_id)
    runs = list(runs_qs.select_related("llm_model", "channel").order_by("created_at")[:limit])

    message_logs_qs = MessageLog.objects.filter(conversation=conversation)
    if run_id is not None:
        message_logs_qs = message_logs_qs.filter(agent_run_id=run_id)
    message_logs = list(
        message_logs_qs.select_related("agent_run").order_by("created_at")[:limit]
    )
    visible_messages = list(
        WebChatMessage.objects.filter(conversation=conversation)
        .order_by("created_at")[:limit]
    )
    task_ids = _extract_task_ids(message_logs)
    tasks = list(Task.objects.filter(user=user, pk__in=task_ids).order_by("created_at"))
    task_audits = list(
        TaskAuditLog.objects.filter(task__user=user, task_id__in=task_ids)
        .select_related("task", "actor")
        .order_by("created_at")
    )

    return {
        "user": _user_summary(user),
        "channel": _channel_summary(conversation.channel),
        "conversation": _conversation_summary(conversation),
        "visible_messages": [_visible_message_summary(msg) for msg in visible_messages],
        "agent_runs": [_run_summary(run, visible_messages) for run in runs],
        "message_logs": [_message_log_summary(log) for log in message_logs],
        "related_tasks": [_task_summary(task) for task in tasks],
        "task_audit_logs": [_task_audit_summary(log) for log in task_audits],
        "automations": [
            _automation_summary(automation)
            for automation in Automation.objects.filter(user=user, is_active=True)
            .order_by("-created_at")
        ],
        "llm_models": [
            _model_summary(model)
            for model in LlmModel.objects.filter(user=user).order_by("-created_at")
        ],
        "limits": {
            "limit": limit,
            "run_id": str(run_id) if run_id else None,
        },
    }


def render_debug_markdown(bundle: dict[str, Any]) -> str:
    lines: list[str] = []
    user = bundle["user"]
    channel = bundle["channel"]
    conversation = bundle["conversation"]
    lines.append("# TaskRaptor Agent Debug Snapshot")
    lines.append("")
    lines.append("## User")
    lines.append(f"- id: `{user['id']}`")
    lines.append(f"- email: `{user['email']}`")
    lines.append(f"- timezone: `{user['timezone']}`")
    lines.append(f"- prompt_instructions_length: {user['prompt_instructions_length']}")
    lines.append("")
    lines.append("## Conversation")
    lines.append(f"- conversation_id: `{conversation['id']}`")
    lines.append(f"- title: {conversation['title'] or '(untitled)'}")
    lines.append(f"- channel_id: `{channel['id']}`")
    lines.append(f"- channel_type: `{channel['type']}`")
    lines.append(f"- channel_name: {channel['name']}")
    lines.append("")

    lines.append("## Visible Chat")
    for msg in bundle["visible_messages"]:
        lines.append(
            f"- [{msg['created_at']}] {msg['role']} "
            f"(id={msg['id']}, agent_run_id={msg['agent_run_id']}): {msg['content']}"
        )
    if not bundle["visible_messages"]:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Agent Runs")
    for run in bundle["agent_runs"]:
        lines.append(
            f"- id=`{run['id']}` status=`{run['status']}` model=`{run['model_key']}` "
            f"input_tokens={run['input_tokens']} output_tokens={run['output_tokens']} "
            f"created_at={run['created_at']} completed_at={run['completed_at']}"
        )
        if run["error"]:
            lines.append(f"  error: {run['error']}")
    if not bundle["agent_runs"]:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Low-Level Message Log")
    for log in bundle["message_logs"]:
        lines.append(
            f"- [{log['created_at']}] run=`{log['agent_run_id']}` actor=`{log['actor']}` "
            f"tool=`{log['tool_name']}` call_id=`{log['tool_call_id']}`"
        )
        if log["metadata"]:
            lines.append(f"  metadata: `{json.dumps(log['metadata'], ensure_ascii=False)}`")
        if log["content"]:
            lines.append(f"  content: {log['content']}")
    if not bundle["message_logs"]:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Related Tasks")
    for task in bundle["related_tasks"]:
        lines.append(
            f"- id=`{task['id']}` name={task['name']!r} status=`{task['status']}` "
            f"priority={task['priority']} due_at={task['due_at']} deleted_at={task['deleted_at']}"
        )
    if not bundle["related_tasks"]:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Task Audit Logs")
    for audit in bundle["task_audit_logs"]:
        lines.append(
            f"- [{audit['created_at']}] task=`{audit['task_id']}` action=`{audit['action']}` "
            f"old={json.dumps(audit['old_value'], ensure_ascii=False)} "
            f"new={json.dumps(audit['new_value'], ensure_ascii=False)} actor={audit['actor_id']}"
        )
    if not bundle["task_audit_logs"]:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Automations")
    for automation in bundle["automations"]:
        lines.append(
            f"- id=`{automation['id']}` active={automation['is_active']} "
            f"schedule_time={automation['schedule_time']} "
            f"last_run_at={automation['last_run_at']} prompt={automation['prompt']!r}"
        )
    if not bundle["automations"]:
        lines.append("- (none)")
    lines.append("")

    lines.append("## LLM Config")
    for model in bundle["llm_models"]:
        lines.append(
            f"- id=`{model['id']}` model_key=`{model['model_key']}` active={model['is_active']} "
            f"api_key={model['api_key']} quota={model['quota']} quota_used={model['quota_used']} "
            f"context_message_limit={model['context_message_limit']}"
        )
    if not bundle["llm_models"]:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def _user_summary(user: User) -> dict[str, Any]:
    prompt = user.prompt_instructions or ""
    return {
        "id": str(user.pk),
        "email": user.email,
        "timezone": user.timezone,
        "prompt_instructions_present": bool(prompt.strip()),
        "prompt_instructions_length": len(prompt),
        "date_joined": _serialize(user.date_joined),
    }


def _channel_summary(channel: Channel) -> dict[str, Any]:
    return {
        "id": str(channel.pk),
        "name": channel.name,
        "type": channel.type,
        "external_id": channel.external_id,
        "archived_at": _serialize(channel.archived_at),
        "created_at": _serialize(channel.created_at),
    }


def _conversation_summary(conversation: Conversation) -> dict[str, Any]:
    return {
        "id": str(conversation.pk),
        "channel_id": str(conversation.channel_id),
        "external_id": conversation.external_id,
        "title": conversation.title,
        "created_at": _serialize(conversation.created_at),
        "updated_at": _serialize(conversation.updated_at),
    }


def _conversation_list_item(conversation: Conversation) -> dict[str, Any]:
    return {
        **_conversation_summary(conversation),
        "channel": _channel_summary(conversation.channel),
        "run_count": conversation.run_count,
        "message_log_count": conversation.message_log_count,
        "visible_message_count": conversation.visible_message_count,
        "latest_run_at": _serialize(conversation.latest_run_at),
        "latest_run_status": conversation.latest_run_status,
        "latest_visible_message": conversation.latest_visible_message or "",
        "latest_visible_role": conversation.latest_visible_role or "",
    }


def _visible_message_summary(message: WebChatMessage) -> dict[str, Any]:
    return {
        "id": str(message.pk),
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "content": message.content,
        "agent_run_id": str(message.agent_run_id) if message.agent_run_id else None,
        "created_at": _serialize(message.created_at),
    }


def _run_summary(run: AgentRun, visible_messages: Iterable[WebChatMessage]) -> dict[str, Any]:
    linked_visible = [
        str(msg.pk)
        for msg in visible_messages
        if msg.agent_run_id is not None and msg.agent_run_id == run.pk
    ]
    logs = list(run.messages.all())
    return {
        "id": str(run.pk),
        "channel_id": str(run.channel_id),
        "conversation_id": str(run.conversation_id),
        "status": run.status,
        "error": run.error,
        "llm_model_id": str(run.llm_model_id),
        "model_key": run.llm_model.model_key,
        "created_at": _serialize(run.created_at),
        "started_at": _serialize(run.started_at),
        "completed_at": _serialize(run.completed_at),
        "input_tokens": sum(log.input_tokens or 0 for log in logs),
        "output_tokens": sum(log.output_tokens or 0 for log in logs),
        "visible_message_ids": linked_visible,
    }


def _message_log_summary(log: MessageLog) -> dict[str, Any]:
    return {
        "id": str(log.pk),
        "agent_run_id": str(log.agent_run_id),
        "conversation_id": str(log.conversation_id),
        "channel_id": str(log.channel_id),
        "actor": log.actor,
        "content": log.content,
        "tool_call_id": log.tool_call_id,
        "tool_name": log.tool_name,
        "metadata": _serialize(log.metadata),
        "input_tokens": log.input_tokens,
        "output_tokens": log.output_tokens,
        "created_at": _serialize(log.created_at),
    }


def _task_summary(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.pk),
        "name": task.name,
        "status": task.status,
        "priority": task.priority,
        "due_at": _serialize(task.due_at),
        "due_type": task.due_type,
        "tags": _serialize(task.tags if isinstance(task.tags, list) else []),
        "remind_at": _serialize(task.remind_at),
        "completed_at": _serialize(task.completed_at),
        "archived_at": _serialize(task.archived_at),
        "deleted_at": _serialize(task.deleted_at),
        "created_at": _serialize(task.created_at),
    }


def _task_audit_summary(log: TaskAuditLog) -> dict[str, Any]:
    return {
        "id": str(log.pk),
        "task_id": str(log.task_id),
        "task_name": log.task.name,
        "created_at": _serialize(log.created_at),
        "action": log.action,
        "old_value": _serialize(log.old_value),
        "new_value": _serialize(log.new_value),
        "actor_id": str(log.actor_id) if log.actor_id else None,
    }


def _automation_summary(automation: Automation) -> dict[str, Any]:
    return {
        "id": str(automation.pk),
        "prompt": automation.prompt,
        "schedule_time": _serialize(automation.schedule_time),
        "is_active": automation.is_active,
        "last_run_at": _serialize(automation.last_run_at),
        "created_at": _serialize(automation.created_at),
        "updated_at": _serialize(automation.updated_at),
    }


def _extract_task_ids(logs: Iterable[MessageLog]) -> set[UUID]:
    task_ids: set[UUID] = set()
    for log in logs:
        if log.tool_name not in {"create_task", "edit_task", "delete_task", "query_tasks"}:
            continue
        if isinstance(log.metadata, dict):
            _collect_task_ids(log.metadata.get("arguments"), task_ids)
        if log.content:
            try:
                _collect_task_ids(json.loads(log.content), task_ids)
            except json.JSONDecodeError:
                pass
    return task_ids


def _collect_task_ids(value: Any, task_ids: set[UUID]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"task_id", "id"} and isinstance(child, str):
                try:
                    task_ids.add(UUID(child))
                except ValueError:
                    pass
            else:
                _collect_task_ids(child, task_ids)
    elif isinstance(value, list):
        for child in value:
            _collect_task_ids(child, task_ids)
