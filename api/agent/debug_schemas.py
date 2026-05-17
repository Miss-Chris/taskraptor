from __future__ import annotations

from typing import Any

from ninja import Schema


class DebugUserOut(Schema):
    id: str
    email: str
    timezone: str | None
    persona: str
    custom_persona_present: bool
    prompt_instructions_present: bool
    prompt_instructions_length: int
    date_joined: str | None


class DebugLlmModelOut(Schema):
    id: str
    model_key: str
    api_key: str
    has_api_key: bool
    quota: int | None
    quota_used: int
    quota_expires_at: str | None
    context_message_limit: int
    is_active: bool
    created_at: str | None
    updated_at: str | None


class DebugSummaryCountsOut(Schema):
    channels: int
    conversations: int
    agent_runs: int
    failed_agent_runs: int
    message_logs: int
    visible_web_messages: int
    tasks: int
    automations: int


class DebugRecentRunItem(Schema):
    id: str
    conversation_id: str
    channel_id: str
    status: str
    model_key: str
    error: str
    created_at: str | None
    started_at: str | None
    completed_at: str | None


class DebugSummaryOut(Schema):
    user: DebugUserOut
    counts: DebugSummaryCountsOut
    recent_runs: list[DebugRecentRunItem]
    llm_models: list[DebugLlmModelOut]


class DebugChannelOut(Schema):
    id: str
    name: str
    type: str
    external_id: str
    archived_at: str | None
    created_at: str | None


class DebugConversationListItemOut(Schema):
    id: str
    channel_id: str
    external_id: str
    title: str
    created_at: str | None
    updated_at: str | None
    channel: DebugChannelOut
    run_count: int
    message_log_count: int
    visible_message_count: int
    latest_run_at: str | None
    latest_run_status: str | None
    latest_visible_message: str
    latest_visible_role: str


class DebugConversationsOut(Schema):
    conversations: list[DebugConversationListItemOut]
    count: int


class DebugConversationOut(Schema):
    id: str
    channel_id: str
    external_id: str
    title: str
    created_at: str | None
    updated_at: str | None


class DebugVisibleMessageOut(Schema):
    id: str
    conversation_id: str
    role: str
    content: str
    agent_run_id: str | None
    created_at: str | None


class DebugAgentRunOut(Schema):
    id: str
    channel_id: str
    conversation_id: str
    status: str
    error: str
    llm_model_id: str
    model_key: str
    created_at: str | None
    started_at: str | None
    completed_at: str | None
    input_tokens: int
    output_tokens: int
    visible_message_ids: list[str]


class DebugMessageLogOut(Schema):
    id: str
    agent_run_id: str
    conversation_id: str
    channel_id: str
    actor: str
    content: str
    tool_call_id: str
    tool_name: str
    metadata: Any
    input_tokens: int | None
    output_tokens: int | None
    created_at: str | None


class DebugRelatedTaskOut(Schema):
    id: str
    name: str
    status: str
    priority: int
    due_at: str | None
    due_type: str
    tags: list[str]
    remind_at: str | None
    reminded_at: str | None
    completed_at: str | None
    archived_at: str | None
    deleted_at: str | None
    created_at: str | None


class DebugTaskAuditLogOut(Schema):
    id: str
    task_id: str
    task_name: str
    created_at: str | None
    action: str
    old_value: Any
    new_value: Any
    actor_id: str | None


class DebugAutomationOut(Schema):
    id: str
    prompt: str
    schedule_time: str | None
    is_active: bool
    last_run_at: str | None
    created_at: str | None
    updated_at: str | None


class DebugBundleLimitsOut(Schema):
    limit: int
    run_id: str | None


class DebugConversationBundleOut(Schema):
    user: DebugUserOut
    channel: DebugChannelOut
    conversation: DebugConversationOut
    visible_messages: list[DebugVisibleMessageOut]
    agent_runs: list[DebugAgentRunOut]
    message_logs: list[DebugMessageLogOut]
    related_tasks: list[DebugRelatedTaskOut]
    task_audit_logs: list[DebugTaskAuditLogOut]
    automations: list[DebugAutomationOut]
    llm_models: list[DebugLlmModelOut]
    limits: DebugBundleLimitsOut
