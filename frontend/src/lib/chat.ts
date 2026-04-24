import { getToken } from "@/lib/auth"

export type ChatMessageRole = string

export type ChatMessage = {
  id: string
  conversation_id: string
  role: ChatMessageRole
  content: string
  agent_run_id: string | null
  created_at: string
}

export type ChatRunStatus = "pending" | "running" | "completed" | "failed" | string

export type ChatRun = {
  id: string
  conversation_id: string
  status: ChatRunStatus
  error: string
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export type ChatConversation = {
  id: string
  title: string
  created_at: string
  updated_at: string
  latest_message: ChatMessage | null
  latest_run: ChatRun | null
}

export type ChatConversationListResponse = {
  conversations: ChatConversation[]
  count: number
}

export type ChatConversationDetailResponse = {
  conversation: ChatConversation
  messages: ChatMessage[]
  runs: ChatRun[]
}

export type ChatMessagesResponse = {
  messages: ChatMessage[]
  count: number
}

export type ChatSendMessageResponse = {
  message: ChatMessage
  run: ChatRun
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken()
  if (!token) {
    throw new Error("Not authenticated")
  }
  return { Authorization: `Bearer ${token}`, ...extra }
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

export async function fetchChatConversations(limit = 20): Promise<ChatConversationListResponse> {
  return getJson(`/api/chat/conversations?limit=${encodeURIComponent(String(limit))}`)
}

export async function createChatConversation(title = ""): Promise<ChatConversation> {
  const res = await fetch("/api/chat/conversations", {
    method: "POST",
    headers: {
      ...authHeaders({ "Content-Type": "application/json" }),
    },
    body: JSON.stringify({ title }),
  })
  if (res.status === 401) {
    throw new Error("SESSION_EXPIRED")
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<ChatConversation>
}

export async function fetchChatConversation(
  conversationId: string,
): Promise<ChatConversationDetailResponse> {
  return getJson(`/api/chat/conversations/${encodeURIComponent(conversationId)}`)
}

export async function fetchChatMessagesAfter(
  conversationId: string,
  afterId: string,
): Promise<ChatMessagesResponse> {
  const params = new URLSearchParams({ after_id: afterId })
  return getJson(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}/messages?${params.toString()}`,
  )
}

export async function sendChatMessage(
  conversationId: string,
  content: string,
): Promise<ChatSendMessageResponse> {
  const res = await fetch(`/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: "POST",
    headers: {
      ...authHeaders({ "Content-Type": "application/json" }),
    },
    body: JSON.stringify({ content }),
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
  return res.json() as Promise<ChatSendMessageResponse>
}

export async function fetchChatRun(runId: string): Promise<ChatRun> {
  return getJson(`/api/chat/runs/${encodeURIComponent(runId)}`)
}
