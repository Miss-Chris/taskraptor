import { getToken } from "@/lib/auth"

export type DebugSummary = {
  user: DebugUser
  counts: Record<string, number>
  recent_runs: DebugAgentRun[]
  llm_models: DebugLlmModel[]
}

export type DebugUser = {
  id: string
  email: string
  timezone: string
  prompt_instructions_present: boolean
  prompt_instructions_length: number
  date_joined: string
}

export type DebugChannel = {
  id: string
  name: string
  type: string
  external_id: string
  archived_at: string | null
  created_at: string
}

export type DebugConversationListItem = {
  id: string
  channel_id: string
  external_id: string
  title: string
  created_at: string
  updated_at: string
  channel: DebugChannel
  run_count: number
  message_log_count: number
  visible_message_count: number
  latest_run_at: string | null
  latest_run_status: string | null
  latest_visible_message: string
  latest_visible_role: string
}

export type DebugVisibleMessage = {
  id: string
  conversation_id: string
  role: string
  content: string
  agent_run_id: string | null
  created_at: string
}

export type DebugAgentRun = {
  id: string
  channel_id: string
  conversation_id: string
  status: string
  error: string
  llm_model_id?: string
  model_key: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  input_tokens?: number
  output_tokens?: number
  visible_message_ids?: string[]
}

export type DebugMessageLog = {
  id: string
  agent_run_id: string
  conversation_id: string
  channel_id: string
  actor: string
  content: string
  tool_call_id: string
  tool_name: string
  metadata: Record<string, unknown>
  input_tokens: number | null
  output_tokens: number | null
  created_at: string
}

export type DebugTask = {
  id: string
  name: string
  status: string
  priority: number
  due_at: string | null
  due_type: string
  tags: string[]
  deleted_at: string | null
  created_at: string
}

export type DebugTaskAuditLog = {
  id: string
  task_id: string
  task_name: string
  created_at: string
  action: string
  old_value: unknown
  new_value: unknown
  actor_id: string | null
}

export type DebugAutomation = {
  id: string
  channel_id: string
  channel_type: string
  prompt: string
  schedule_time: string
  is_active: boolean
  last_run_at: string | null
}

export type DebugLlmModel = {
  id: string
  model_key: string
  api_key: string
  has_api_key: boolean
  quota: number | null
  quota_used: number
  quota_expires_at: string | null
  context_message_limit: number
  is_active: boolean
}

export type DebugConversationBundle = {
  user: DebugUser
  channel: DebugChannel
  conversation: {
    id: string
    channel_id: string
    external_id: string
    title: string
    created_at: string
    updated_at: string
  }
  visible_messages: DebugVisibleMessage[]
  agent_runs: DebugAgentRun[]
  message_logs: DebugMessageLog[]
  related_tasks: DebugTask[]
  task_audit_logs: DebugTaskAuditLog[]
  automations: DebugAutomation[]
  llm_models: DebugLlmModel[]
  limits: {
    limit: number
    run_id: string | null
  }
}

function authHeaders(): HeadersInit {
  const token = getToken()
  if (!token) {
    throw new Error("Not authenticated")
  }
  return { Authorization: `Bearer ${token}` }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown }
    if (typeof data.detail === "string") return data.detail
  } catch {
    /* ignore */
  }
  return res.statusText || "Request failed"
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    headers: { ...authHeaders() },
  })
  if (res.status === 401) {
    throw new Error("SESSION_EXPIRED")
  }
  if (res.status === 404) {
    throw new Error("NOT_FOUND")
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<T>
}

export async function fetchDebugSummary(): Promise<DebugSummary> {
  return getJson<DebugSummary>("/api/debug/summary")
}

export async function fetchDebugConversations(): Promise<{
  conversations: DebugConversationListItem[]
  count: number
}> {
  return getJson("/api/debug/conversations")
}

export async function fetchDebugConversation(
  conversationId: string,
): Promise<DebugConversationBundle> {
  return getJson(`/api/debug/conversations/${encodeURIComponent(conversationId)}`)
}
