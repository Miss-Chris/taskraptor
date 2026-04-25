import { type FormEvent, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { X } from "lucide-react"

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

type DueType = "date" | "time" | "none"
type PriorityLevel = "low" | "medium" | "high" | "urgent"
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

const PRIORITY_OPTIONS: {
  value: PriorityLevel
  label: string
  numeric: number
}[] = [
  { value: "low", label: "Low", numeric: 0 },
  { value: "medium", label: "Medium", numeric: 3 },
  { value: "high", label: "High", numeric: 7 },
  { value: "urgent", label: "Urgent", numeric: 10 },
]

function numericToPriorityLevel(n: number): PriorityLevel {
  if (n >= 8) return "urgent"
  if (n >= 5) return "high"
  if (n >= 2) return "medium"
  return "low"
}

const DUE_TYPE_OPTIONS: { value: DueType; label: string }[] = [
  { value: "date", label: "Date only" },
  { value: "time", label: "Date + time" },
  { value: "none", label: "No date" },
]

const CONTROL_CLASS =
  "h-9 w-full rounded-3xl border border-transparent bg-input/50 px-3 py-1 text-base outline-none transition-[color,box-shadow,background-color] focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"

function getInitialDueType(task: Task | null | undefined): DueType {
  if (!task?.due_at) return "none"
  return task.due_type === "date" ? "date" : "time"
}

function getInitialDueAt(task: Task | null | undefined): string {
  if (!task?.due_at) return ""
  if (task.due_type === "date") {
    return (
      task.due_date_local ??
      task.due_at_local?.slice(0, 10) ??
      task.due_at.slice(0, 10)
    )
  }
  return task.due_at_local?.slice(0, 16) ?? task.due_at.slice(0, 16)
}

function dueInputType(dueType: DueType): "date" | "datetime-local" {
  return dueType === "date" ? "date" : "datetime-local"
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
  const [priority, setPriority] = useState<PriorityLevel>(
    numericToPriorityLevel(task?.priority ?? 0)
  )
  const [dueType, setDueType] = useState<DueType>(getInitialDueType(task))
  const [dueAt, setDueAt] = useState(getInitialDueAt(task))
  const [tags, setTags] = useState<string[]>(task?.tags ?? [])
  const [tagInput, setTagInput] = useState("")
  const tagInputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const isSubmitting = createTask.isPending || updateTask.isPending

  function addTag(value: string) {
    const tag = value.trim()
    if (tag && !tags.includes(tag)) {
      setTags((prev) => [...prev, tag])
    }
    setTagInput("")
  }

  function removeTag(tag: string) {
    setTags((prev) => prev.filter((t) => t !== tag))
  }

  function handleTagKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault()
      addTag(tagInput)
    } else if (e.key === "Backspace" && tagInput === "" && tags.length > 0) {
      setTags((prev) => prev.slice(0, -1))
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    const trimmedName = name.trim()
    if (!trimmedName) {
      setError("Name is required")
      return
    }

    const parsedPriority =
      PRIORITY_OPTIONS.find((p) => p.value === priority)?.numeric ?? 0

    const apiDueType: "date" | "time" = dueType === "none" ? "date" : dueType
    const nextDueAt =
      dueType !== "none" ? (dueAt.trim() || undefined) : undefined

    // Flush any pending tag text on submit
    const finalTags =
      tagInput.trim() ? [...tags, tagInput.trim()] : tags

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
          due_type: apiDueType,
          tags: finalTags,
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
          due_type: apiDueType,
          tags: finalTags,
        }
        if (nextDueAt) {
          body.due_at = nextDueAt
        }
        const savedTask = await createTask.mutateAsync({ body })
        onSaved?.(savedTask)
      }
      onOpenChange(false)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to save task"
      if (
        message === "SESSION_EXPIRED" ||
        message === "Not authenticated"
      ) {
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
          <DialogTitle>
            {isEditMode ? "Edit task" : "New task"}
          </DialogTitle>
          <DialogDescription>
            {isEditMode
              ? "Update the task details used by the web app and agent tools."
              : "Create a task that can be managed from the web app or by the agent."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} noValidate>
          <div className="grid gap-3 py-3">
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}

            {/* Name */}
            <div className="grid gap-1.5">
              <Label htmlFor="task-name">Name</Label>
              <Input
                id="task-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="File taxes"
                autoComplete="off"
              />
            </div>

            {/* Status + Priority */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-1.5">
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
              <div className="grid gap-1.5">
                <Label htmlFor="task-priority">Priority</Label>
                <select
                  id="task-priority"
                  value={priority}
                  onChange={(e) =>
                    setPriority(e.target.value as PriorityLevel)
                  }
                  className={CONTROL_CLASS}
                >
                  {PRIORITY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Due date — segmented control + optional date picker */}
            <div className="grid gap-1.5">
              <Label>Due</Label>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                {/* Segmented control */}
                <div className="inline-flex shrink-0 rounded-3xl bg-input/50 p-0.5">
                  {DUE_TYPE_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setDueType(option.value)
                        if (option.value === "none") setDueAt("")
                      }}
                      className={cn(
                        "rounded-[20px] px-3 py-1 text-sm transition-colors",
                        dueType === option.value
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                {dueType !== "none" && (
                  <Input
                    id="task-due-at"
                    type={dueInputType(dueType)}
                    value={dueAt}
                    onChange={(e) => setDueAt(e.target.value)}
                    className="sm:flex-1"
                  />
                )}
              </div>
            </div>

            {/* Tags — chip-in-input pattern */}
            <div className="grid gap-1.5">
              <Label htmlFor="task-tag-input">Tags</Label>
              {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
              <div
                className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-3xl border border-transparent bg-input/50 px-3 py-1.5 transition-[color,box-shadow,background-color] focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30 cursor-text"
                onClick={() => tagInputRef.current?.focus()}
              >
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary/50 px-2 py-0.5 text-xs text-secondary-foreground"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeTag(tag)
                      }}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                <input
                  ref={tagInputRef}
                  id="task-tag-input"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagKeyDown}
                  onBlur={() => {
                    if (tagInput.trim()) addTag(tagInput)
                  }}
                  placeholder={tags.length === 0 ? "Add tags…" : ""}
                  className="min-w-[80px] flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button
                type="button"
                variant="outline"
                disabled={isSubmitting}
              >
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
