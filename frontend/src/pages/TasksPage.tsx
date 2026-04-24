import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { IconChevronRight, IconListDetails } from "@tabler/icons-react"

import { TaskList } from "@/components/tasks/TaskList"
import { TaskTag } from "@/components/tasks/TaskTag"
import { Skeleton } from "@/components/ui/skeleton"
import { clearToken } from "@/lib/auth"
import {
  fetchTask,
  fetchTaskAuditLogs,
  fetchTasks,
  type Task,
  type TaskAuditLog,
} from "@/lib/tasks"
import { cn } from "@/lib/utils"

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All tasks" },
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
]

function formatTs(iso: string | null): string {
  if (!iso) return "None"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "None"
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "None"
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : "None"
  if (typeof value === "object") return JSON.stringify(value)
  return String(value).replace(/_/g, " ")
}

function formatAuditAction(action: string): string {
  const labels: Record<string, string> = {
    status_changed: "Status changed",
    name_changed: "Name changed",
    priority_changed: "Priority changed",
    tags_changed: "Tags changed",
    deleted: "Deleted",
  }
  return labels[action] ?? action.replace(/_/g, " ")
}

function DetailRow({
  label,
  value,
}: {
  label: string
  value: string | number
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm font-medium">{value}</dd>
    </div>
  )
}

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
  cancelled: "bg-muted-foreground",
}

function TaskStatusIndicator({ status }: { status: Task["status"] }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
      <span className={cn("size-2 rounded-full", STATUS_DOT_CLASS[status])} />
      {STATUS_LABEL[status] ?? status.replace(/_/g, " ")}
    </span>
  )
}

function HistoryRow({ audit }: { audit: TaskAuditLog }) {
  return (
    <li className="border-b border-border py-3 last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {formatAuditAction(audit.action)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {formatTs(audit.created_at)}
          </p>
        </div>
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
        {formatValue(audit.old_value)}{" "}
        <IconChevronRight className="mx-1 inline size-3" />{" "}
        <span className="text-foreground">{formatValue(audit.new_value)}</span>
      </p>
    </li>
  )
}

export function TasksPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tag = searchParams.get("tag") ?? ""
  const status = searchParams.get("status") ?? ""
  const requestedTaskId = searchParams.get("task")

  const [tasks, setTasks] = useState<Task[]>([])
  const [tasksLoading, setTasksLoading] = useState(true)
  const [tasksError, setTasksError] = useState<string | null>(null)
  const [taskDetail, setTaskDetail] = useState<Task | null>(null)
  const [history, setHistory] = useState<TaskAuditLog[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  const selectedTaskId = useMemo(() => {
    if (requestedTaskId && tasks.some((task) => task.id === requestedTaskId)) {
      return requestedTaskId
    }
    return tasks[0]?.id ?? null
  }, [requestedTaskId, tasks])

  const selectedListTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, tasks]
  )
  const selectedTask = taskDetail ?? selectedListTask

  const handleSessionError = useCallback(
    (msg: string) => {
      if (msg === "SESSION_EXPIRED") {
        clearToken()
        navigate("/login", { replace: true })
        return true
      }
      return false
    },
    [navigate]
  )

  const loadTasks = useCallback(async () => {
    setTasksLoading(true)
    setTasksError(null)
    try {
      const res = await fetchTasks({
        tag: tag.trim() || undefined,
        status: status.trim() || undefined,
      })
      setTasks(res.tasks)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load tasks"
      if (handleSessionError(msg)) return
      setTasksError(msg)
      setTasks([])
    } finally {
      setTasksLoading(false)
    }
  }, [handleSessionError, status, tag])

  useEffect(() => {
    void loadTasks()
  }, [loadTasks])

  useEffect(() => {
    if (!selectedTaskId) {
      setTaskDetail(null)
      setHistory([])
      setDetailError(null)
      setDetailLoading(false)
      return
    }

    let cancelled = false
    setDetailLoading(true)
    setDetailError(null)
    setTaskDetail(null)
    setHistory([])
    ;(async () => {
      try {
        const [task, auditResponse] = await Promise.all([
          fetchTask(selectedTaskId),
          fetchTaskAuditLogs(selectedTaskId),
        ])
        if (cancelled) return
        setTaskDetail(task)
        setHistory(auditResponse.audit_logs)
      } catch (e) {
        if (cancelled) return
        const msg =
          e instanceof Error ? e.message : "Failed to load task details"
        if (handleSessionError(msg)) return
        setDetailError(msg === "NOT_FOUND" ? "Task not found." : msg)
      } finally {
        if (!cancelled) setDetailLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [handleSessionError, selectedTaskId])

  function updateFilters(next: {
    status?: string
    tag?: string
    task?: string | null
  }) {
    const nextParams = new URLSearchParams(searchParams)
    if (next.status !== undefined) {
      if (next.status) nextParams.set("status", next.status)
      else nextParams.delete("status")
    }
    if (next.tag !== undefined) {
      if (next.tag) nextParams.set("tag", next.tag)
      else nextParams.delete("tag")
    }
    if (next.task !== undefined) {
      if (next.task) nextParams.set("task", next.task)
      else nextParams.delete("task")
    }
    setSearchParams(nextParams, { replace: true })
  }

  function selectTask(task: Task) {
    updateFilters({ task: task.id })
  }

  const title = tag
    ? `#${tag}`
    : (STATUS_OPTIONS.find((option) => option.value === status)?.label ??
      "Tasks")
  const activeFilterLabel = tag
    ? `Tagged ${tag}`
    : status
      ? STATUS_OPTIONS.find((option) => option.value === status)?.label
      : "All tasks"

  return (
    <div className="grid h-full min-h-[calc(100vh-7rem)] w-full gap-4 lg:grid-cols-[minmax(24rem,0.9fr)_minmax(24rem,1.1fr)]">
      <section className="flex min-h-[24rem] flex-col overflow-hidden rounded-lg border border-border bg-card/40">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold">{title}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {tasksLoading
                ? "Loading tasks"
                : `${tasks.length} task${tasks.length === 1 ? "" : "s"}`}
            </p>
          </div>
          {activeFilterLabel ? (
            <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
              {activeFilterLabel}
            </span>
          ) : null}
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <TaskList
            tasks={tasks}
            loading={tasksLoading}
            error={tasksError}
            emptyMessage="No tasks match this view."
            selectedTaskId={selectedTaskId}
            onSelectTask={selectTask}
          />
        </div>
      </section>

      <section className="flex min-h-[24rem] flex-col overflow-hidden rounded-lg border border-border bg-card/40">
        {!selectedTaskId ? (
          <div className="flex min-h-[24rem] flex-col items-center justify-center p-6 text-center">
            <IconListDetails className="mb-3 size-8 text-muted-foreground" />
            <h2 className="text-base font-semibold">No task selected</h2>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              Select a task from the list to see its details and recent history.
            </p>
          </div>
        ) : (
          <>
            <div className="border-b border-border px-5 py-4">
              {selectedTask ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <h2 className="min-w-0 flex-1 text-lg leading-snug font-semibold">
                      {selectedTask.name}
                    </h2>
                    <TaskStatusIndicator status={selectedTask.status} />
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedTask.tags.length > 0 ? (
                      selectedTask.tags.map((taskTag) => (
                        <TaskTag key={taskTag} label={taskTag} />
                      ))
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        No tags
                      </span>
                    )}
                  </div>
                </div>
              ) : detailLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-6 w-4/5 rounded-md" />
                  <Skeleton className="h-5 w-28 rounded-md" />
                </div>
              ) : null}
            </div>

            <div className="min-h-0 flex-1 overflow-auto">
              {detailError ? (
                <p className="p-5 text-sm text-destructive" role="alert">
                  {detailError}
                </p>
              ) : selectedTask ? (
                <div className="space-y-6 p-5">
                  <dl className="grid grid-cols-2 gap-4">
                    <DetailRow label="Priority" value={selectedTask.priority} />
                    <DetailRow label="Due type" value={selectedTask.due_type} />
                    <DetailRow
                      label="Due"
                      value={formatTs(selectedTask.due_at)}
                    />
                    <DetailRow
                      label="Reminder"
                      value={formatTs(selectedTask.remind_at)}
                    />
                    <DetailRow
                      label="Completed"
                      value={formatTs(selectedTask.completed_at)}
                    />
                    <DetailRow
                      label="Created"
                      value={formatTs(selectedTask.created_at)}
                    />
                  </dl>

                  <section>
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-sm font-semibold">History</h3>
                      {detailLoading ? (
                        <span className="text-xs text-muted-foreground">
                          Refreshing
                        </span>
                      ) : null}
                    </div>
                    {detailLoading && history.length === 0 ? (
                      <div className="space-y-2">
                        {Array.from({ length: 3 }).map((_, i) => (
                          <Skeleton
                            key={i}
                            className="h-14 w-full rounded-md"
                          />
                        ))}
                      </div>
                    ) : history.length > 0 ? (
                      <ul className="rounded-md border border-border px-3">
                        {history.map((audit) => (
                          <HistoryRow key={audit.id} audit={audit} />
                        ))}
                      </ul>
                    ) : (
                      <p className="rounded-md border p-3 text-sm text-muted-foreground">
                        No changes recorded for this task yet.
                      </p>
                    )}
                  </section>
                </div>
              ) : detailLoading ? (
                <div className="space-y-5 p-5">
                  <Skeleton className="h-20 w-full rounded-md" />
                  <Skeleton className="h-32 w-full rounded-md" />
                </div>
              ) : null}
            </div>
          </>
        )}
      </section>
    </div>
  )
}
