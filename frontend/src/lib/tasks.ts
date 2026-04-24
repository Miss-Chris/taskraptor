import { getToken } from "@/lib/auth"

export type TaskStatus = "pending" | "in_progress" | "completed" | "cancelled"

export type Task = {
  id: string
  name: string
  status: TaskStatus
  priority: number
  due_at: string | null
  due_type: "date" | "time"
  tags: string[]
  remind_at: string | null
  completed_at: string | null
  archived_at: string | null
  created_at: string
}

export type TaskAuditLog = {
  id: string
  task_id: string
  created_at: string
  action: string
  old_value: unknown
  new_value: unknown
  actor_id: string | null
}

export type TaskListResponse = {
  tasks: Task[]
  count: number
}

export type TaskAuditLogListResponse = {
  audit_logs: TaskAuditLog[]
}

export type StatusCountItem = {
  status: string
  count: number
}

export type TagCountItem = {
  tag: string
  count: number
}

export type TaskFacets = {
  status_counts: StatusCountItem[]
  tag_counts: TagCountItem[]
  total: number
}

export type ListTasksParams = {
  status?: string
  tag?: string
  upcoming?: boolean
  priority?: number
  min_priority?: number
  max_priority?: number
}

function authHeaders(): HeadersInit {
  const token = getToken()
  if (!token) {
    throw new Error("Not authenticated")
  }
  return { Authorization: `Bearer ${token}` }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown }
    if (typeof data.detail === "string") return data.detail
  } catch {
    /* ignore */
  }
  return res.statusText || "Request failed"
}

function buildListQuery(params: ListTasksParams): string {
  const sp = new URLSearchParams()
  if (params.status !== undefined && params.status !== "") {
    sp.set("status", params.status)
  }
  if (params.tag !== undefined && params.tag !== "") {
    sp.set("tag", params.tag)
  }
  if (params.upcoming === true) {
    sp.set("upcoming", "true")
  }
  if (params.priority !== undefined) {
    sp.set("priority", String(params.priority))
  }
  if (params.min_priority !== undefined) {
    sp.set("min_priority", String(params.min_priority))
  }
  if (params.max_priority !== undefined) {
    sp.set("max_priority", String(params.max_priority))
  }
  const q = sp.toString()
  return q ? `?${q}` : ""
}

export async function fetchTaskFacets(): Promise<TaskFacets> {
  const res = await fetch("/api/tasks/facets", {
    headers: { ...authHeaders() },
  })
  if (res.status === 401) {
    throw new Error("SESSION_EXPIRED")
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<TaskFacets>
}

export async function fetchTasks(
  params: ListTasksParams = {}
): Promise<TaskListResponse> {
  const res = await fetch(`/api/tasks/${buildListQuery(params)}`, {
    headers: { ...authHeaders() },
  })
  if (res.status === 401) {
    throw new Error("SESSION_EXPIRED")
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<TaskListResponse>
}

export async function fetchTask(taskId: string): Promise<Task> {
  const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, {
    headers: { ...authHeaders() },
  })
  if (res.status === 401) {
    throw new Error("SESSION_EXPIRED")
  }
  if (res.status === 404) {
    throw new Error("NOT_FOUND")
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<Task>
}

export async function fetchTaskAuditLogs(
  taskId: string
): Promise<TaskAuditLogListResponse> {
  const res = await fetch(
    `/api/tasks/${encodeURIComponent(taskId)}/audit-logs`,
    {
      headers: { ...authHeaders() },
    }
  )
  if (res.status === 401) {
    throw new Error("SESSION_EXPIRED")
  }
  if (res.status === 404) {
    throw new Error("NOT_FOUND")
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<TaskAuditLogListResponse>
}

export function sortTasksByDueAtAsc(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    if (!a.due_at && !b.due_at) return 0
    if (!a.due_at) return 1
    if (!b.due_at) return -1
    return new Date(a.due_at).getTime() - new Date(b.due_at).getTime()
  })
}
