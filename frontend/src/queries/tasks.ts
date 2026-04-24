import { $api } from "@/lib/api/client"
import { toListTasksQuery, type ListTasksParams } from "@/lib/tasks"

export function useTaskFacetsQuery() {
  return $api.useQuery("get", "/api/tasks/facets", {}, { retry: false })
}

export function useTasksQuery(
  params: ListTasksParams,
  options?: { enabled?: boolean }
) {
  const query = toListTasksQuery(params)
  return $api.useQuery(
    "get",
    "/api/tasks/",
    { params: { query } },
    { ...options, retry: false }
  )
}

export function useTaskQuery(
  taskId: string | undefined,
  options?: { enabled?: boolean }
) {
  return $api.useQuery(
    "get",
    "/api/tasks/{task_id}",
    {
      params: { path: { task_id: taskId ?? "" } },
    },
    {
      enabled: Boolean(taskId) && options?.enabled !== false,
      retry: false,
    }
  )
}

export function useTaskAuditLogsQuery(
  taskId: string | undefined,
  options?: { enabled?: boolean }
) {
  return $api.useQuery(
    "get",
    "/api/tasks/{task_id}/audit-logs",
    {
      params: { path: { task_id: taskId ?? "" } },
    },
    {
      enabled: Boolean(taskId) && options?.enabled !== false,
      retry: false,
    }
  )
}
