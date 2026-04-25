import { type FormEvent, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"

import { TaskTag } from "@/components/tasks/TaskTag"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { endSession } from "@/lib/auth"
import { cn } from "@/lib/utils"
import {
  type Task,
  type TaskCreateIn,
  type TaskStatus,
  type TaskUpdateIn,
} from "@/lib/tasks"
import {
  useCreateTaskMutation,
  useUpdateTaskMutation,
} from "@/queries/tasks"

type DueType = "date" | "time"
type Mode = "create" | "edit"

type TaskFormDialogProps = {
  mode: Mode
  task?: Task | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved?: (task: Task) => void
}

const STATUS_OPTIONS: { value: TaskStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
]

const DUE_TYPE_OPTIONS: { value: DueType; label: string }[] = [
  { value: "time", label: "Date and time" },
  { value: "date", label: "Date only" },
]

const CONTROL_CLASS =
  "h-9 w-full rounded-3xl border border-transparent bg-input/50 px-3 py-1 text-base outline-none transition-[color,box-shadow,background-color] focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"

function getInitialDueType(task: Task | null | undefined): DueType {
  return task?.due_type === "date" ? "date" : "time"
}

function getInitialDueAt(task: Task | null | undefined): string {
  if (!task?.due_at) return ""
  if (task.due_type === "date") {
    return task.due_date_local ?? task.due_at_local?.slice(0, 10) ?? task.due_at.slice(0, 10)
  }
  return task.due_at_local?.slice(0, 16) ?? task.due_at.slice(0, 16)
}

function parseTags(value: string): string[] {
  const seen = new Set<string>()
  const tags: string[] = []
  for (const rawTag of value.split(",")) {
    const tag = rawTag.trim()
    if (!tag || seen.has(tag)) continue
    seen.add(tag)
    tags.push(tag)
  }
  return tags
}

function dueInputType(dueType: DueType): "date" | "datetime-local" {
  return dueType === "date" ? "date" : "datetime-local"
}

function buildDueAt(dueType: DueType, value: string): string | undefined {
  const trimmed = value.trim()
  if (!trimmed) return undefined
  return dueType === "date" ? trimmed : trimmed
}

export function TaskFormDialog({
  mode,
  task,
  open,
  onOpenChange,
  onSaved,
}: TaskFormDialogProps) {
  const isEditMode = mode === "edit"
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const createTask = useCreateTaskMutation()
  const updateTask = useUpdateTaskMutation()
  const [name, setName] = useState(task?.name ?? "")
  const [status, setStatus] = useState<TaskStatus>(
    (task?.status as TaskStatus | undefined) ?? "pending"
  )
  const [priority, setPriority] = useState(String(task?.priority ?? 0))
  const [dueType, setDueType] = useState<DueType>(getInitialDueType(task))
  const [dueAt, setDueAt] = useState(getInitialDueAt(task))
  const [tagsText, setTagsText] = useState((task?.tags ?? []).join(", "))
  const [error, setError] = useState<string | null>(null)
  const tags = parseTags(tagsText)
  const isSubmitting = createTask.isPending || updateTask.isPending

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    const trimmedName = name.trim()
    if (!trimmedName) {
      setError("Name is required")
      return
    }

    const parsedPriority = priority.trim() === "" ? 0 : Number(priority)
    if (!Number.isInteger(parsedPriority)) {
      setError("Priority must be a whole number")
      return
    }

    const nextDueAt = buildDueAt(dueType, dueAt)

    try {
      if (isEditMode) {
        if (!task) {
          setError("Select a task before editing")
          return
        }
        const body: TaskUpdateIn = {
          name: trimmedName,
          status,
          priority: parsedPriority,
          due_type: dueType,
          tags,
        }
        if (nextDueAt) {
          body.due_at = nextDueAt
        } else if (task.due_at) {
          body.clear_due_at = true
        }
        const savedTask = await updateTask.mutateAsync({
          params: { path: { task_id: task.id } },
          body,
        })
        onSaved?.(savedTask)
      } else {
        const body: TaskCreateIn = {
          name: trimmedName,
          status,
          priority: parsedPriority,
          due_type: dueType,
          tags,
        }
        if (nextDueAt) {
          body.due_at = nextDueAt
        }
        const savedTask = await createTask.mutateAsync({ body })
        onSaved?.(savedTask)
      }
      onOpenChange(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save task"
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
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditMode ? "Edit task" : "New task"}</DialogTitle>
          <DialogDescription>
            {isEditMode
              ? "Update the task details used by the web app and agent tools."
              : "Create a task that can be managed from the web app or by the agent."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
            <div className="grid gap-2">
              <Label htmlFor="task-name">Name</Label>
              <Input
                id="task-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="File taxes"
                required
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="task-status">Status</Label>
                <select
                  id="task-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value as TaskStatus)}
                  className={CONTROL_CLASS}
                >
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="task-priority">Priority</Label>
                <Input
                  id="task-priority"
                  type="number"
                  step="1"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="task-due-type">Due type</Label>
                <select
                  id="task-due-type"
                  value={dueType}
                  onChange={(e) => setDueType(e.target.value as DueType)}
                  className={CONTROL_CLASS}
                >
                  {DUE_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="task-due-at">Due</Label>
                <Input
                  id="task-due-at"
                  type={dueInputType(dueType)}
                  value={dueAt}
                  onChange={(e) => setDueAt(e.target.value)}
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="task-tags">Tags</Label>
              <Input
                id="task-tags"
                value={tagsText}
                onChange={(e) => setTagsText(e.target.value)}
                placeholder="personal, urgent"
              />
              <div
                className={cn(
                  "flex min-h-6 flex-wrap gap-1.5",
                  tags.length === 0 && "hidden"
                )}
              >
                {tags.map((tag) => (
                  <TaskTag key={tag} label={tag} />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={isSubmitting}>
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? isEditMode
                  ? "Saving..."
                  : "Creating..."
                : isEditMode
                  ? "Save changes"
                  : "Create task"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
