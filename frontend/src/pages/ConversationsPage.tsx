import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate } from "react-router-dom"

import { DeleteConversationDialog } from "@/components/chat/DeleteConversationDialog"
import { Button } from "@/components/ui/button"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { endSession } from "@/lib/auth"
import { type ChatConversation } from "@/lib/chat"
import { cn } from "@/lib/utils"
import { useChatConversationsQuery } from "@/queries/chat"
import { IconMessagePlus, IconTrash } from "@tabler/icons-react"

function conversationTitle(conversation: ChatConversation): string {
  const title = conversation.title.trim()
  if (title) return title
  const latest = conversation.latest_message?.content.trim()
  if (latest) return latest
  return "New chat"
}

function conversationPreview(conversation: ChatConversation): string {
  return conversation.latest_message?.content.trim() || "No messages yet"
}

function formatUpdatedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

export function ConversationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const conversationsQuery = useChatConversationsQuery(200)
  const [deleteTarget, setDeleteTarget] = useState<ChatConversation | null>(
    null
  )

  useDocumentTitle("All conversations")

  useEffect(() => {
    const err = conversationsQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      endSession(queryClient)
      navigate("/login", { replace: true })
    }
  }, [conversationsQuery.error, navigate, queryClient])

  const conversations = conversationsQuery.data?.conversations ?? []

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5">
      <header className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-page-title">All Conversations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {conversationsQuery.data?.count ?? conversations.length} active
            chats
          </p>
        </div>
        <Button type="button" onClick={() => navigate("/")}>
          <IconMessagePlus />
          New Chat
        </Button>
      </header>

      {conversationsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">
          Loading conversations...
        </p>
      ) : conversationsQuery.isError ? (
        <p className="text-sm text-destructive">Could not load conversations</p>
      ) : conversations.length > 0 ? (
        <div className="divide-y divide-border rounded-lg border border-border">
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 p-3 sm:p-4"
            >
              <Link
                to={`/c/${conversation.id}`}
                className={cn(
                  "min-w-0 rounded-md outline-none",
                  "focus-visible:ring-3 focus-visible:ring-ring/30"
                )}
              >
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <h2 className="truncate text-sm font-medium">
                    {conversationTitle(conversation)}
                  </h2>
                  <time className="shrink-0 text-xs text-muted-foreground">
                    {formatUpdatedAt(conversation.updated_at)}
                  </time>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                  {conversationPreview(conversation)}
                </p>
              </Link>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Delete conversation"
                onClick={() => setDeleteTarget(conversation)}
              >
                <IconTrash />
                <span className="sr-only">Delete conversation</span>
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex min-h-[18rem] flex-col items-center justify-center gap-4 text-center">
          <p className="text-sm text-muted-foreground">No conversations yet.</p>
          <Button type="button" onClick={() => navigate("/")}>
            <IconMessagePlus />
            New Chat
          </Button>
        </div>
      )}

      <DeleteConversationDialog
        conversation={deleteTarget}
        open={deleteTarget != null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        onDeleted={() => {
          void conversationsQuery.refetch()
        }}
        onAuthExpired={() => navigate("/login", { replace: true })}
      />
    </div>
  )
}
