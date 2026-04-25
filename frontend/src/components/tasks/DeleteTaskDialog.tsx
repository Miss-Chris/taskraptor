import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"

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
import { endSession } from "@/lib/auth"
import type { Task } from "@/lib/tasks"
import { useDeleteTaskMutation } from "@/queries/tasks"

type DeleteTaskDialogProps = {
  task: Task | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted?: (taskId: string) => void
}

function taskLabel(task: Task | null): string {
  const name = task?.name.trim()
  return name ? name : "this task"
}

export function DeleteTaskDialog({
  task,
  open,
  onOpenChange,
  onDeleted,
}: DeleteTaskDialogProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const deleteTask = useDeleteTaskMutation()
  const [error, setError] = useState<string | null>(null)

  async function handleDelete() {
    if (!task) return
    setError(null)
    try {
      await deleteTask.mutateAsync({
        params: { path: { task_id: task.id } },
      })
      onDeleted?.(task.id)
      onOpenChange(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete task"
      if (message === "SESSION_EXPIRED" || message === "Not authenticated") {
        endSession(queryClient)
        navigate("/login", { replace: true })
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
          <DialogTitle>Delete task?</DialogTitle>
          <DialogDescription>
            This removes "{taskLabel(task)}" from your task list. The task is
            soft-deleted and will no longer appear in the web app.
          </DialogDescription>
        </DialogHeader>
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={deleteTask.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteTask.isPending || !task}
          >
            {deleteTask.isPending ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
