import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge"
import { TaskTag } from "@/components/tasks/TaskTag"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { clearToken } from "@/lib/auth"
import { fetchTask, type Task } from "@/lib/tasks"

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
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!taskId) {
      setError("Missing task id")
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const t = await fetchTask(taskId)
      setTask(t)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load task"
      if (msg === "SESSION_EXPIRED") {
        clearToken()
        navigate("/login", { replace: true })
        return
      }
      if (msg === "NOT_FOUND") {
        setError("Task not found.")
        setTask(null)
      } else {
        setError(msg)
        setTask(null)
      }
    } finally {
      setLoading(false)
    }
  }, [navigate, taskId])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      await load()
      if (cancelled) return
    })()
    return () => {
      cancelled = true
    }
  }, [load])

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </div>
    )
  }

  if (error || !task) {
    return (
      <div className="mx-auto w-full max-w-2xl space-y-4">
        <p className="text-destructive text-sm" role="alert">
          {error ?? "Could not load task."}
        </p>
        <Button type="button" variant="outline" asChild>
          <Link to="/tasks">Back to tasks</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" size="sm" asChild>
          <Link to="/tasks">← All tasks</Link>
        </Button>
      </div>

      <Card>
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-xl">{task.name}</CardTitle>
            <TaskStatusBadge status={task.status} />
          </div>
          <CardDescription>Task id: {task.id}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 text-sm">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Priority</dt>
              <dd className="font-medium">{task.priority}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Due type</dt>
              <dd className="font-medium capitalize">{task.due_type}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Due at</dt>
              <dd className="font-medium">{formatTs(task.due_at)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Remind at</dt>
              <dd className="font-medium">{formatTs(task.remind_at)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Completed at</dt>
              <dd className="font-medium">{formatTs(task.completed_at)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Archived at</dt>
              <dd className="font-medium">{formatTs(task.archived_at)}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-muted-foreground">Created at</dt>
              <dd className="font-medium">{formatTs(task.created_at)}</dd>
            </div>
          </dl>

          <div>
            <h3 className="text-muted-foreground mb-2 text-xs font-medium tracking-wide uppercase">
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

          <p className="text-muted-foreground text-xs leading-relaxed">
            Changes from chat or the agent are not shown here yet; this view is read-only from the
            API.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
