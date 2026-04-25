import { useQueryClient } from "@tanstack/react-query"

import { $api } from "@/lib/api/client"
import { toListTasksQuery, type ListTasksParams } from "@/lib/tasks"

function tasksQueryKey() {
  return ["get", "/api/tasks/"] as const
}

function taskFacetsQueryKey() {
  return ["get", "/api/tasks/facets"] as const
}

function taskQueryKey() {
  return ["get", "/api/tasks/{task_id}"] as const
}

function taskAuditLogsQueryKey() {
  return ["get", "/api/tasks/{task_id}/audit-logs"] as const
}

function invalidateTaskCollections(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: tasksQueryKey() })
  void queryClient.invalidateQueries({ queryKey: taskFacetsQueryKey() })
}

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

export function useCreateTaskMutation() {
  const queryClient = useQueryClient()
  return $api.useMutation("post", "/api/tasks/", {
    onSuccess() {
      invalidateTaskCollections(queryClient)
    },
  })
}

export function useUpdateTaskMutation() {
  const queryClient = useQueryClient()
  return $api.useMutation("patch", "/api/tasks/{task_id}", {
    onSuccess() {
      invalidateTaskCollections(queryClient)
      void queryClient.invalidateQueries({ queryKey: taskQueryKey() })
      void queryClient.invalidateQueries({ queryKey: taskAuditLogsQueryKey() })
    },
  })
}

export function useDeleteTaskMutation() {
  const queryClient = useQueryClient()
  return $api.useMutation("delete", "/api/tasks/{task_id}", {
    onSuccess() {
      invalidateTaskCollections(queryClient)
      void queryClient.invalidateQueries({ queryKey: taskQueryKey() })
      void queryClient.invalidateQueries({ queryKey: taskAuditLogsQueryKey() })
    },
  })
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
