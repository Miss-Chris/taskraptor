import { cn } from "@/lib/utils"
import type { TaskStatus } from "@/lib/tasks"

const STATUS_LABEL: Record<TaskStatus, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
}

const STATUS_CLASS: Record<TaskStatus, string> = {
  pending: "bg-amber-500/15 text-amber-200 border-amber-500/30",
  in_progress: "bg-sky-500/15 text-sky-200 border-sky-500/30",
  completed: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
  cancelled: "bg-muted text-muted-foreground border-border",
}

export function TaskStatusBadge({ status }: { status: string }) {
  const s = status as TaskStatus
  const label = STATUS_LABEL[s] ?? status.replace(/_/g, " ")
  const cls = STATUS_CLASS[s] ?? "bg-muted text-muted-foreground border-border"

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium capitalize",
        cls,
      )}
    >
      {label}
    </span>
  )
}
