import { useEffect, useMemo } from "react"
import { useNavigate } from "react-router-dom"

import { TaskList } from "@/components/tasks/TaskList"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { clearToken } from "@/lib/auth"
import { sortTasksByDueAtAsc } from "@/lib/tasks"
import { useTasksQuery } from "@/queries/tasks"

export function UpcomingTasksPage() {
  const navigate = useNavigate()
  const listParams = useMemo(() => ({ upcoming: true as const }), [])
  const tasksQuery = useTasksQuery(listParams)
  const tasks = sortTasksByDueAtAsc(tasksQuery.data?.tasks ?? [])
  const loading = tasksQuery.isLoading
  const error = tasksQuery.isError
    ? tasksQuery.error instanceof Error
      ? tasksQuery.error.message
      : "Failed to load tasks"
    : null

  useEffect(() => {
    const err = tasksQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      clearToken()
      navigate("/login", { replace: true })
    }
  }, [tasksQuery.error, navigate])

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
