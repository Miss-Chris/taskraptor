import { fetchClient } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type ChatMessage = components["schemas"]["ChatMessageOut"]
export type ChatMessageRole = ChatMessage["role"]

export type ChatRun = components["schemas"]["ChatRunOut"]
export type ChatRunStatus = ChatRun["status"]

export type ChatConversation = components["schemas"]["ChatConversationOut"]
export type ChatMessagesResponse = components["schemas"]["ChatMessagesOut"]

function requireData<T>(data: T | undefined): T {
  if (data === undefined || data === null) {
    throw new Error("Request failed")
  }
  return data
}

export async function fetchChatMessagesAfter(
  conversationId: string,
  afterId: string
): Promise<ChatMessagesResponse> {
  const { data } = await fetchClient.GET(
    "/api/chat/conversations/{conversation_id}/messages",
    {
      params: {
        path: { conversation_id: conversationId },
        query: { after_id: afterId },
      },
    }
  )
  return requireData(data)
}

export async function fetchChatRun(runId: string): Promise<ChatRun> {
  const { data } = await fetchClient.GET("/api/chat/runs/{run_id}", {
    params: { path: { run_id: runId } },
  })
  return requireData(data)
}
