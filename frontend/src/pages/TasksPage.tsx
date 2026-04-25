import { useMemo } from "react"
import { useSearchParams } from "react-router-dom"

import { TaskExplorer } from "@/components/tasks/TaskExplorer"
import { useDocumentTitle } from "@/hooks/use-document-title"

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All tasks" },
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
]

export function TasksPage() {
  const [searchParams] = useSearchParams()
  const tag = searchParams.get("tag") ?? ""
  const status = searchParams.get("status") ?? ""

  const listParams = useMemo(
    () => ({
      tag: tag.trim() || undefined,
      status: status.trim() || undefined,
    }),
    [tag, status]
  )

  const title = tag
    ? `#${tag}`
    : (STATUS_OPTIONS.find((option) => option.value === status)?.label ??
      "Tasks")
  useDocumentTitle(title)

  const activeFilterLabel = tag
    ? `Tagged ${tag}`
    : status
      ? STATUS_OPTIONS.find((option) => option.value === status)?.label
      : "All tasks"

  return (
    <TaskExplorer
      listParams={listParams}
      title={title}
      activeFilterLabel={activeFilterLabel}
      emptyMessage="No tasks match this view."
    />
  )
}
