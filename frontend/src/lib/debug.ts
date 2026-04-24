import { fetchClient } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type DebugSummary = components["schemas"]["DebugSummaryOut"]
export type DebugUser = components["schemas"]["DebugUserOut"]
export type DebugChannel = components["schemas"]["DebugChannelOut"]
export type DebugConversationListItem = components["schemas"]["DebugConversationListItemOut"]
export type DebugVisibleMessage = components["schemas"]["DebugVisibleMessageOut"]
export type DebugAgentRun = components["schemas"]["DebugAgentRunOut"]
export type DebugMessageLog = components["schemas"]["DebugMessageLogOut"]
export type DebugTask = components["schemas"]["DebugRelatedTaskOut"]
export type DebugTaskAuditLog = components["schemas"]["DebugTaskAuditLogOut"]
export type DebugAutomation = components["schemas"]["DebugAutomationOut"]
export type DebugLlmModel = components["schemas"]["DebugLlmModelOut"]
export type DebugConversationBundle = components["schemas"]["DebugConversationBundleOut"]

function requireData<T>(data: T | undefined): T {
  if (data === undefined || data === null) {
    throw new Error("Request failed")
  }
  return data
}

export type DebugConversationsList = components["schemas"]["DebugConversationsOut"]

export async function fetchDebugConversations(): Promise<DebugConversationsList> {
  const { data } = await fetchClient.GET("/api/debug/conversations", {})
  return requireData(data)
}

export async function fetchDebugConversation(
  conversationId: string
): Promise<DebugConversationBundle> {
  const { data } = await fetchClient.GET(
    "/api/debug/conversations/{conversation_id}",
    {
      params: { path: { conversation_id: conversationId } },
    }
  )
  return requireData(data)
}
