import { Link } from "react-router-dom"

import { formatTaskDue, type Task } from "@/lib/tasks"
import { TaskTag } from "@/components/tasks/TaskTag"
import { cn } from "@/lib/utils"

const STATUS_LABEL: Record<Task["status"], string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
}

const STATUS_DOT_CLASS: Record<Task["status"], string> = {
  pending: "bg-amber-400",
  in_progress: "bg-sky-400",
  completed: "bg-emerald-400",
  cancelled: "bg-muted-foreground/50",
}

const STATUS_BORDER_CLASS: Record<Task["status"], string> = {
  pending: "border-l-amber-400",
  in_progress: "border-l-sky-400",
  completed: "border-l-emerald-400",
  cancelled: "border-l-muted-foreground/50",
}

function TaskItemContent({ task }: { task: Task }) {
  return (
    <>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate font-medium text-foreground">
            {task.name}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-md border border-border/60 px-1.5 py-0.5 text-xs text-muted-foreground",
            )}
          >
            <span
              className={cn(
                "size-1.5 rounded-full",
                STATUS_DOT_CLASS[task.status],
              )}
            />
            {STATUS_LABEL[task.status]}
          </span>
          {task.tags.map((t) => (
            <TaskTag key={t} label={t} />
          ))}
        </div>
      </div>
      <div className="flex shrink-0 flex-col gap-1 text-right md:text-left">
        <span className="text-xs text-muted-foreground">
          Due{" "}
          <span className="font-medium text-foreground">
            {formatTaskDue(task)}
          </span>
        </span>
        <span className="text-xs text-muted-foreground">
          Priority{" "}
          <span className="font-medium text-foreground">{task.priority}</span>
        </span>
      </div>
    </>
  )
}

export function TaskItem({
  task,
  className,
  selected = false,
  onSelect,
}: {
  task: Task
  className?: string
  selected?: boolean
  onSelect?: (task: Task) => void
}) {
  const itemClassName = cn(
    "flex w-full flex-col gap-2 rounded-lg border border-l-4 border-border bg-card/40 px-4 py-3 text-left transition-colors hover:bg-accent/30 md:flex-row md:items-center md:justify-between",
    STATUS_BORDER_CLASS[task.status],
    selected && "bg-accent/60 ring-1 ring-primary/50",
    className
  )

  if (onSelect) {
    return (
      <button
        type="button"
        aria-pressed={selected}
        className={itemClassName}
        onClick={() => onSelect(task)}
      >
        <TaskItemContent task={task} />
      </button>
    )
  }

  return (
    <Link to={`/tasks/${task.id}`} className={itemClassName}>
      <TaskItemContent task={task} />
    </Link>
  )
}
