import { fetchClient } from "@/lib/api/client"
import type { components, operations } from "@/lib/api/schema"

export type Task = components["schemas"]["TaskOut"]
export type TaskStatus = "pending" | "in_progress" | "completed" | "cancelled"

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
