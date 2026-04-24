import { useMemo } from "react"

import { TaskExplorer } from "@/components/tasks/TaskExplorer"
import { sortTasksByDueAtAsc } from "@/lib/tasks"

export function UpcomingTasksPage() {
  const listParams = useMemo(() => ({ upcoming: true as const }), [])

  return (
    <TaskExplorer
      listParams={listParams}
      title="Upcoming tasks"
      activeFilterLabel="Upcoming"
      emptyMessage="No upcoming tasks. Add due dates to your tasks to see them here."
      transformTasks={sortTasksByDueAtAsc}
    />
  )
}
