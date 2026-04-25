import { fetchClient } from "@/lib/api/client"
import type { components, operations } from "@/lib/api/schema"

export type Task = components["schemas"]["TaskOut"]
export type TaskStatus = "pending" | "in_progress" | "completed" | "cancelled"
export type TaskCreateIn = components["schemas"]["TaskCreateIn"]
export type TaskUpdateIn = components["schemas"]["TaskUpdateIn"]

export type TaskAuditLog = components["schemas"]["TaskAuditLogOut"]
export type TaskListResponse = components["schemas"]["TaskListOut"]
export type TaskAuditLogListResponse = components["schemas"]["TaskAuditLogListOut"]
export type StatusCountItem = components["schemas"]["StatusCountItem"]
export type TagCountItem = components["schemas"]["TagCountItem"]
export type TaskFacets = components["schemas"]["TaskFacetsOut"]

export type ListTasksParams = {
  status?: string
  tag?: string
  upcoming?: boolean
  priority?: number
  min_priority?: number
  max_priority?: number
}

function requireData<T>(data: T | undefined): T {
  if (data === undefined || data === null) {
    throw new Error("Request failed")
  }
  return data
}

export function toListTasksQuery(
  params: ListTasksParams
): NonNullable<operations["tasks_api_list_tasks"]["parameters"]["query"]> {
  const q: NonNullable<operations["tasks_api_list_tasks"]["parameters"]["query"]> = {}
  if (params.status !== undefined && params.status !== "") {
    q.status = params.status
  }
  if (params.tag !== undefined && params.tag !== "") {
    q.tag = params.tag
  }
  if (params.upcoming === true) {
    q.upcoming = true
  }
  if (params.priority !== undefined) {
    q.priority = params.priority
  }
  if (params.min_priority !== undefined) {
    q.min_priority = params.min_priority
  }
  if (params.max_priority !== undefined) {
    q.max_priority = params.max_priority
  }
  return q
}

export async function fetchTaskFacets(): Promise<TaskFacets> {
  const { data } = await fetchClient.GET("/api/tasks/facets", {})
  return requireData(data)
}

export async function fetchTasks(
  params: ListTasksParams = {}
): Promise<TaskListResponse> {
  const query = toListTasksQuery(params)
  const { data } = await fetchClient.GET("/api/tasks/", {
    params: { query },
  })
  return requireData(data)
}

export async function fetchTask(taskId: string): Promise<Task> {
  const { data } = await fetchClient.GET("/api/tasks/{task_id}", {
    params: { path: { task_id: taskId } },
  })
  return requireData(data)
}

export async function createTask(payload: TaskCreateIn): Promise<Task> {
  const { data } = await fetchClient.POST("/api/tasks/", {
    body: payload,
  })
  return requireData(data)
}

export async function updateTask(
  taskId: string,
  payload: TaskUpdateIn
): Promise<Task> {
  const { data } = await fetchClient.PATCH("/api/tasks/{task_id}", {
    params: { path: { task_id: taskId } },
    body: payload,
  })
  return requireData(data)
}

export async function deleteTask(taskId: string): Promise<void> {
  await fetchClient.DELETE("/api/tasks/{task_id}", {
    params: { path: { task_id: taskId } },
  })
}

export async function fetchTaskAuditLogs(
  taskId: string
): Promise<TaskAuditLogListResponse> {
  const { data } = await fetchClient.GET(
    "/api/tasks/{task_id}/audit-logs",
    {
      params: { path: { task_id: taskId } },
    }
  )
  return requireData(data)
}

export function sortTasksByDueAtAsc(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    if (!a.due_at && !b.due_at) return 0
    if (!a.due_at) return 1
    if (!b.due_at) return -1
    return new Date(a.due_at).getTime() - new Date(b.due_at).getTime()
  })
}

function parseLocalDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return null

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return null
  }

  return new Date(year, month - 1, day)
}

function formatWithTimezone(
  iso: string | null | undefined,
  timeZone: string | null | undefined,
  options: Intl.DateTimeFormatOptions
): string {
  if (!iso) return "—"
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return "—"

  try {
    return new Intl.DateTimeFormat(undefined, {
      ...options,
      ...(timeZone ? { timeZone } : {}),
    }).format(date)
  } catch {
    return date.toLocaleString(undefined, options)
  }
}

export function formatTaskDue(task: Task): string {
  const dateOptions: Intl.DateTimeFormatOptions = {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  }

  if (task.due_type === "date") {
    const localDate = parseLocalDate(task.due_date_local)
    if (localDate) {
      return localDate.toLocaleDateString(undefined, dateOptions)
    }
    return formatWithTimezone(task.due_at, task.timezone, dateOptions)
  }

  return formatWithTimezone(task.due_at, task.timezone, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}
