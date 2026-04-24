import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

import { TaskList } from "@/components/tasks/TaskList"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { clearToken } from "@/lib/auth"
import { fetchTasks, sortTasksByDueAtAsc, type Task } from "@/lib/tasks"

export function UpcomingTasksPage() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchTasks({ upcoming: true })
      setTasks(sortTasksByDueAtAsc(res.tasks))
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
  }, [navigate])

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

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <Card>
        <CardHeader className="space-y-1">
          <CardTitle>Upcoming tasks</CardTitle>
          <CardDescription>
            Tasks with a due date on or after now, excluding completed. Sorted by due date.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TaskList
            tasks={tasks}
            loading={loading}
            error={error}
            emptyMessage="No upcoming tasks. Add due dates to your tasks to see them here."
          />
        </CardContent>
      </Card>
    </div>
  )
}
