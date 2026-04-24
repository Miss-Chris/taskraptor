import type { Task } from "@/lib/tasks"
import { TaskItem } from "@/components/tasks/TaskItem"
import { Skeleton } from "@/components/ui/skeleton"

export function TaskList({
  tasks,
  loading,
  error,
  emptyMessage,
  selectedTaskId,
  onSelectTask,
}: {
  tasks: Task[]
  loading: boolean
  error: string | null
  emptyMessage: string
  selectedTaskId?: string | null
  onSelectTask?: (task: Task) => void
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
      <p className="text-sm text-destructive" role="alert">
        {error}
      </p>
    )
  }

  if (tasks.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>
  }

  return (
    <ul className="space-y-3">
      {tasks.map((task) => (
        <li key={task.id}>
          <TaskItem
            task={task}
            selected={selectedTaskId === task.id}
            onSelect={onSelectTask}
          />
        </li>
      ))}
    </ul>
  )
}
