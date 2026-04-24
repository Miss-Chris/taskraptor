import { Link } from "react-router-dom"

import type { Task } from "@/lib/tasks"
import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge"
import { TaskTag } from "@/components/tasks/TaskTag"
import { cn } from "@/lib/utils"

function formatDue(dueAt: string | null, dueType: Task["due_type"]): string {
  if (!dueAt) return "—"
  const d = new Date(dueAt)
  if (Number.isNaN(d.getTime())) return "—"
  if (dueType === "date") {
    return d.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  }
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

export function TaskItem({ task, className }: { task: Task; className?: string }) {
  return (
    <Link
      to={`/tasks/${task.id}`}
      className={cn(
        "flex flex-col gap-2 rounded-lg border border-border bg-card/40 px-4 py-3 transition-colors hover:bg-accent/30 md:flex-row md:items-center md:justify-between",
        className,
      )}
    >
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate font-medium text-foreground">{task.name}</span>
          <TaskStatusBadge status={task.status} />
        </div>
        {task.tags.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {task.tags.map((t) => (
              <TaskTag key={t} label={t} />
            ))}
          </div>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-col gap-1 text-right text-sm text-muted-foreground md:text-left">
        <span>
          Due: <span className="text-foreground">{formatDue(task.due_at, task.due_type)}</span>
        </span>
        <span className="text-xs">Priority {task.priority}</span>
      </div>
    </Link>
  )
}
