import { useCallback, useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { TaskList } from "@/components/tasks/TaskList"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { clearToken } from "@/lib/auth"
import { fetchTasks, type Task } from "@/lib/tasks"

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
]

export function TasksPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tag = searchParams.get("tag") ?? ""
  const status = searchParams.get("status") ?? ""

  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const tagParam = tag.trim() || undefined
      const statusParam = status.trim() || undefined
      const res = await fetchTasks({
        tag: tagParam,
        status: statusParam,
      })
      setTasks(res.tasks)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load tasks"
      if (msg === "SESSION_EXPIRED") {
        clearToken()
        navigate("/login", { replace: true })
        return
      }
      setError(msg)
      setTasks([])
    } finally {
      setLoading(false)
    }
  }, [navigate, tag, status])

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

  function setStatusFilter(next: string) {
    const nextParams = new URLSearchParams(searchParams)
    if (next === "") {
      nextParams.delete("status")
    } else {
      nextParams.set("status", next)
    }
    setSearchParams(nextParams, { replace: true })
  }

  function clearTag() {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete("tag")
    setSearchParams(nextParams, { replace: true })
  }

  const title = tag ? `Tasks tagged “${tag}”` : "All tasks"
  const description =
    tag || status
      ? "Filtered from your workspace. Clear filters to see everything."
      : "Everything that is not deleted."

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <Card>
        <CardHeader className="space-y-1">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
            <div className="space-y-2">
              <Label htmlFor="task-status-filter">Status</Label>
              <select
                id="task-status-filter"
                className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-9 w-full min-w-[10rem] rounded-md border px-3 py-1 text-sm shadow-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 sm:w-48"
                value={status}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value || "all"} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            {tag ? (
              <Button type="button" variant="outline" size="sm" onClick={clearTag} className="w-fit">
                Clear tag filter
              </Button>
            ) : null}
          </div>

          <TaskList
            tasks={tasks}
            loading={loading}
            error={error}
            emptyMessage="No tasks match these filters. Create tasks via chat or your agent when that’s available."
          />
        </CardContent>
      </Card>
    </div>
  )
}
