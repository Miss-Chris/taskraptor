import { useEffect, useMemo, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearchParams } from "react-router-dom"
import {
  IconChevronRight,
  IconDots,
  IconListDetails,
  IconPencil,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react"

import { DeleteTaskDialog } from "@/components/tasks/DeleteTaskDialog"
import { TaskFormDialog } from "@/components/tasks/TaskFormDialog"
import { TaskList } from "@/components/tasks/TaskList"
import { TaskTag } from "@/components/tasks/TaskTag"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { endSession } from "@/lib/auth"
import { cn } from "@/lib/utils"
import {
  formatTaskDue,
  type ListTasksParams,
  type Task,
  type TaskAuditLog,
} from "@/lib/tasks"
import {
  useTaskAuditLogsQuery,
  useTaskQuery,
  useTasksQuery,
} from "@/queries/tasks"

function formatTs(iso: string | null): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function formatTsShort(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—"
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : "—"
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
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-semibold">{value}</dd>
    </div>
  )
}

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
}

const STATUS_DOT_CLASS: Record<string, string> = {
  pending: "bg-amber-400",
  in_progress: "bg-sky-400",
  completed: "bg-emerald-400",
  cancelled: "bg-muted-foreground",
}

function TaskStatusIndicator({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
      <span
        className={cn("size-2 rounded-full", STATUS_DOT_CLASS[status] ?? "bg-muted-foreground")}
      />
      {STATUS_LABEL[status] ?? status.replace(/_/g, " ")}
    </span>
  )
}

function HistoryRow({ audit }: { audit: TaskAuditLog }) {
  const time = formatTsShort(audit.created_at)
  return (
    <li className="flex items-baseline gap-1 border-b border-border py-2 text-xs last:border-b-0">
      <span className="font-medium text-foreground">
        {formatAuditAction(audit.action)}:
      </span>
      <span className="text-muted-foreground">
        {formatValue(audit.old_value)}
      </span>
      <IconChevronRight className="inline size-3 shrink-0 text-muted-foreground/50" />
      <span className="text-foreground">{formatValue(audit.new_value)}</span>
      {time ? (
        <>
          <span className="text-muted-foreground/50">·</span>
          <span className="text-muted-foreground">{time}</span>
        </>
      ) : null}
    </li>
  )
}

export function TaskExplorer({
  listParams,
  title,
  activeFilterLabel,
  emptyMessage,
  transformTasks,
}: {
  listParams: ListTasksParams
  title: string
  activeFilterLabel?: string | null
  emptyMessage: string
  transformTasks?: (tasks: Task[]) => Task[]
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const requestedTaskId = searchParams.get("task")
  const tasksQuery = useTasksQuery(listParams)
  const tasks = useMemo(() => {
    const list = tasksQuery.data?.tasks ?? []
    return transformTasks ? transformTasks(list) : list
  }, [tasksQuery.data, transformTasks])
  const tasksLoading = tasksQuery.isLoading
  const tasksError = tasksQuery.isError
    ? tasksQuery.error instanceof Error
      ? tasksQuery.error.message
      : "Failed to load tasks"
    : null

  const selectedTaskId = useMemo(() => {
    if (requestedTaskId && tasks.some((task) => task.id === requestedTaskId)) {
      return requestedTaskId
    }
    return tasks[0]?.id ?? null
  }, [requestedTaskId, tasks])

  const taskQuery = useTaskQuery(selectedTaskId ?? undefined)
  const auditQuery = useTaskAuditLogsQuery(selectedTaskId ?? undefined)

  const selectedListTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, tasks]
  )
  const selectedTask = taskQuery.data ?? selectedListTask
  const history = auditQuery.data?.audit_logs ?? []
  const detailError = useMemo(() => {
    if (taskQuery.isError) {
      const m = taskQuery.error instanceof Error ? taskQuery.error.message : "Error"
      return m === "NOT_FOUND" ? "Task not found." : m
    }
    if (auditQuery.isError) {
      return auditQuery.error instanceof Error
        ? auditQuery.error.message
        : "Failed to load history"
    }
    return null
  }, [taskQuery.isError, taskQuery.error, auditQuery.isError, auditQuery.error])

  const detailLoading =
    Boolean(selectedTaskId) &&
    (taskQuery.isPending || auditQuery.isPending) &&
    !taskQuery.isError &&
    !auditQuery.isError

  useEffect(() => {
    const err = tasksQuery.error ?? taskQuery.error ?? auditQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      endSession(queryClient)
      navigate("/login", { replace: true })
    }
  }, [tasksQuery.error, taskQuery.error, auditQuery.error, navigate, queryClient])

  function setSelectedTask(taskId: string) {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set("task", taskId)
    setSearchParams(nextParams, { replace: true })
  }

  function clearSelectedTask() {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete("task")
    setSearchParams(nextParams, { replace: true })
  }

  function selectTask(task: Task) {
    setSelectedTask(task.id)
  }

  return (
    <>
    <div className="grid h-full min-h-[calc(100vh-7rem)] w-full gap-4 lg:grid-cols-[minmax(24rem,0.9fr)_minmax(24rem,1.1fr)]">
      <section className="flex min-h-[24rem] flex-col overflow-hidden rounded-lg border border-border bg-card/40">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-bold">{title}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {tasksLoading
                ? "Loading tasks"
                : `${tasks.length} task${tasks.length === 1 ? "" : "s"}`}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            {activeFilterLabel ? (
              <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
                {activeFilterLabel}
              </span>
            ) : null}
            <Button
              type="button"
              size="sm"
              onClick={() => setCreateDialogOpen(true)}
            >
              <IconPlus />
              New task
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <TaskList
            tasks={tasks}
            loading={tasksLoading}
            error={tasksError}
            emptyMessage={emptyMessage}
            selectedTaskId={selectedTaskId}
            onSelectTask={selectTask}
          />
        </div>
      </section>

      <section className="flex min-h-[24rem] flex-col overflow-hidden rounded-lg border border-border bg-card/40">
        {!selectedTaskId ? (
          <div className="flex min-h-[24rem] flex-col items-center justify-center p-6 text-center">
            <IconListDetails className="mb-3 size-8 text-muted-foreground" />
            {!tasksLoading && tasks.length === 0 ? (
              <>
                <h2 className="text-base font-semibold">No tasks here</h2>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  Create a new task to get started.
                </p>
              </>
            ) : (
              <>
                <h2 className="text-base font-semibold">No task selected</h2>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  Select a task from the list to see its details and recent
                  history.
                </p>
              </>
            )}
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
                    <div className="flex shrink-0 items-center gap-2">
                      <TaskStatusIndicator status={selectedTask.status} />
                      <Button
                        type="button"
                        variant="outline"
                        size="xs"
                        onClick={() => setEditDialogOpen(true)}
                      >
                        <IconPencil />
                        Edit
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            aria-label="More options"
                          >
                            <IconDots />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onSelect={() => setDeleteDialogOpen(true)}
                          >
                            <IconTrash className="size-4" />
                            Delete task
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
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
                      value={formatTaskDue(selectedTask)}
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
                      <h3 className="text-section-title">History</h3>
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
    <TaskFormDialog
      key={createDialogOpen ? "create-task-open" : "create-task-closed"}
      mode="create"
      open={createDialogOpen}
      onOpenChange={setCreateDialogOpen}
      onSaved={(task) => setSelectedTask(task.id)}
    />
    <TaskFormDialog
      key={
        selectedTask
          ? `edit-${selectedTask.id}-${editDialogOpen ? "open" : "closed"}`
          : "edit-task"
      }
      mode="edit"
      task={selectedTask}
      open={editDialogOpen}
      onOpenChange={setEditDialogOpen}
      onSaved={(task) => setSelectedTask(task.id)}
    />
    <DeleteTaskDialog
      task={selectedTask}
      open={deleteDialogOpen}
      onOpenChange={setDeleteDialogOpen}
      onDeleted={clearSelectedTask}
    />
    </>
  )
}
