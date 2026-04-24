import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { clearToken } from "@/lib/auth"
import { type ChatConversation } from "@/lib/chat"
import { useDeleteChatConversationMutation } from "@/queries/chat"

type DeleteConversationDialogProps = {
  conversation: ChatConversation | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted: (conversationId: string) => void
  onAuthExpired: () => void
}

function conversationLabel(conversation: ChatConversation | null): string {
  if (!conversation) return "this conversation"
  const title = conversation.title.trim()
  if (title) return title
  const latest = conversation.latest_message?.content.trim()
  if (latest) return latest
  return "this conversation"
}

export function DeleteConversationDialog({
  conversation,
  open,
  onOpenChange,
  onDeleted,
  onAuthExpired,
}: DeleteConversationDialogProps) {
  const deleteConversation = useDeleteChatConversationMutation()
  const [error, setError] = useState<string | null>(null)

  async function handleDelete() {
    if (!conversation) return
    setError(null)
    try {
      await deleteConversation.mutateAsync({
        params: { path: { conversation_id: conversation.id } },
      })
      window.dispatchEvent(new Event("taskraptor:chat-updated"))
      onDeleted(conversation.id)
      onOpenChange(false)
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to delete conversation"
      if (message === "SESSION_EXPIRED" || message === "Not authenticated") {
        clearToken()
        onAuthExpired()
        return
      }
      setError(message)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) setError(null)
        onOpenChange(nextOpen)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete conversation?</DialogTitle>
          <DialogDescription>
            This removes "{conversationLabel(conversation)}" from your chat list.
          </DialogDescription>
        </DialogHeader>
        {error ? <p className="text-destructive text-sm">{error}</p> : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteConversation.isPending || !conversation}
          >
            {deleteConversation.isPending ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
