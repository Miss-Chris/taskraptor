import { useQueryClient } from "@tanstack/react-query"

import { $api } from "@/lib/api/client"

function automationsQueryKey() {
  return ["get", "/api/automations/"] as const
}

export function useAutomationsQuery() {
  return $api.useQuery("get", "/api/automations/", {}, { retry: false })
}

export function useAutomationQuery(
  automationId: string | undefined,
  options?: { enabled?: boolean }
) {
  return $api.useQuery(
    "get",
    "/api/automations/{automation_id}",
    {
      params: { path: { automation_id: automationId ?? "" } },
    },
    {
      enabled: Boolean(automationId) && options?.enabled !== false,
      retry: false,
    }
  )
}

export function useCreateAutomationMutation() {
  const queryClient = useQueryClient()
  return $api.useMutation("post", "/api/automations/", {
    onSuccess() {
      void queryClient.invalidateQueries({ queryKey: automationsQueryKey() })
    },
  })
}

export function useUpdateAutomationMutation() {
  const queryClient = useQueryClient()
  return $api.useMutation("patch", "/api/automations/{automation_id}", {
    onSuccess() {
      void queryClient.invalidateQueries({ queryKey: automationsQueryKey() })
    },
  })
}

export function useDeleteAutomationMutation() {
  const queryClient = useQueryClient()
  return $api.useMutation("delete", "/api/automations/{automation_id}", {
    onSuccess() {
      void queryClient.invalidateQueries({ queryKey: automationsQueryKey() })
    },
  })
}
