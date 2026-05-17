from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ninja import Schema


class UsageLlmModelOut(Schema):
    id: UUID
    model_key: str
    provider: str
    display_name: str
    has_api_key: bool
    quota: int | None
    quota_used: int
    quota_remaining: int | None
    quota_expires_at: datetime | None
    context_message_limit: int
    is_active: bool
    is_system: bool
    is_available: bool
    supports_image_input: bool
    created_at: datetime
    updated_at: datetime


class UsageSystemQuotaOut(Schema):
    model_id: UUID
    quota: int | None
    quota_used: int
    quota_remaining: int | None
    quota_expires_at: datetime | None
    is_available: bool
    is_active: bool


class UsageTotalsOut(Schema):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    recent_run_count: int
    failed_run_count: int
    recent_since: datetime


class SupportedModelOptionOut(Schema):
    model_key: str
    provider: str
    display_name: str
    requires_api_key: bool
    supports_image_input: bool


class UsageSummaryOut(Schema):
    system_model: UsageSystemQuotaOut
    totals: UsageTotalsOut
    models: list[UsageLlmModelOut]
    supported_models: list[SupportedModelOptionOut]


class UsageModelCreateIn(Schema):
    model_key: str
    api_key: str
    context_message_limit: int = 25
    is_active: bool = True


class UsageModelUpdateIn(Schema):
    api_key: str | None = None
    context_message_limit: int | None = None
    is_active: bool | None = None
