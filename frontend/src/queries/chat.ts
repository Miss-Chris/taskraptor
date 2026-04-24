import { $api } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type ChatConversationDetail = components["schemas"]["ChatConversationDetailOut"]

export function useChatConversationQuery(conversationId: string | undefined) {
  return $api.useQuery(
    "get",
    "/api/chat/conversations/{conversation_id}",
    {
      params: {
        path: { conversation_id: conversationId ?? "" },
      },
    },
    {
      enabled: Boolean(conversationId),
      retry: false,
    },
  )
}

export function useChatConversationsQuery(limit = 20) {
  return $api.useQuery(
    "get",
    "/api/chat/conversations",
    { params: { query: { limit } } },
    { retry: false }
  )
}

export function useCreateChatConversationMutation() {
  return $api.useMutation("post", "/api/chat/conversations")
}

export function useSendChatMessageMutation() {
  return $api.useMutation(
    "post",
    "/api/chat/conversations/{conversation_id}/messages"
  )
}
