import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge"
import { TaskTag } from "@/components/tasks/TaskTag"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { endSession } from "@/lib/auth"
import { formatTaskDue, type Task } from "@/lib/tasks"
import { useTaskQuery } from "@/queries/tasks"

function formatTs(iso: string | null): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const taskQuery = useTaskQuery(taskId, { enabled: Boolean(taskId) })
  const task: Task | null = taskQuery.data ?? null
  const loading = Boolean(taskId) && taskQuery.isLoading
  const error = !taskId
    ? "Missing task id"
    : taskQuery.isError
      ? taskQuery.error instanceof Error
        ? taskQuery.error.message === "NOT_FOUND"
          ? "Task not found."
          : taskQuery.error.message
        : "Failed to load task"
      : null

  useDocumentTitle(
    loading
      ? "Loading task"
      : task?.name || (error === "Task not found." ? "Task not found" : "Task")
  )

  useEffect(() => {
    const err = taskQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      endSession(queryClient)
      navigate("/login", { replace: true })
    }
  }, [taskQuery.error, navigate, queryClient])

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-4xl">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (error || !task) {
    return (
      <div className="mx-auto w-full max-w-4xl space-y-4">
        <p className="text-sm text-destructive" role="alert">
          {error ?? "Could not load task."}
        </p>
        <Button type="button" variant="outline" asChild>
          <Link to="/tasks">Back to tasks</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" size="sm" asChild>
          <Link to="/tasks">← All tasks</Link>
        </Button>
      </div>

      <Card>
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-xl font-bold">{task.name}</CardTitle>
            <TaskStatusBadge status={task.status} />
          </div>
          <CardDescription>Task id: {task.id}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 text-sm">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-label">Priority</dt>
              <dd className="font-medium">{task.priority}</dd>
            </div>
            <div>
              <dt className="text-label">Due type</dt>
              <dd className="font-medium capitalize">{task.due_type}</dd>
            </div>
            <div>
              <dt className="text-label">Due at</dt>
              <dd className="font-medium">{formatTaskDue(task)}</dd>
            </div>
            <div>
              <dt className="text-label">Remind at</dt>
              <dd className="font-medium">{formatTs(task.remind_at)}</dd>
            </div>
            <div>
              <dt className="text-label">Completed at</dt>
              <dd className="font-medium">{formatTs(task.completed_at)}</dd>
            </div>
            <div>
              <dt className="text-label">Archived at</dt>
              <dd className="font-medium">{formatTs(task.archived_at)}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-label">Created at</dt>
              <dd className="font-medium">{formatTs(task.created_at)}</dd>
            </div>
          </dl>

          <div>
            <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Tags
            </h3>
            {task.tags.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {task.tags.map((t) => (
                  <TaskTag key={t} label={t} />
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground">No tags</p>
            )}
          </div>

          <p className="text-xs leading-relaxed text-muted-foreground">
            Changes from chat or the agent are not shown here yet; this view is
            read-only from the API.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
