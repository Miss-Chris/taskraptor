import type { Task } from "@/lib/tasks"
import { TaskItem } from "@/components/tasks/TaskItem"
import { Skeleton } from "@/components/ui/skeleton"

export function TaskList({
  tasks,
  loading,
  error,
  emptyMessage,
}: {
  tasks: Task[]
  loading: boolean
  error: string | null
  emptyMessage: string
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <p className="text-destructive text-sm" role="alert">
        {error}
      </p>
    )
  }

  if (tasks.length === 0) {
    return <p className="text-muted-foreground text-sm">{emptyMessage}</p>
  }

  return (
    <ul className="space-y-3">
      {tasks.map((task) => (
        <li key={task.id}>
          <TaskItem task={task} />
        </li>
      ))}
    </ul>
  )
}
