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
