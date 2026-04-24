import { useQueryClient } from "@tanstack/react-query"

import { $api } from "@/lib/api/client"

function usageSummaryQueryKey() {
  return ["get", "/api/usage/summary"] as const
}

function useInvalidateUsageSummary() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: usageSummaryQueryKey() })
  }
}

export function useUsageSummaryQuery() {
  return $api.useQuery("get", "/api/usage/summary", {}, { retry: false })
}

export function useCreateLlmModelMutation() {
  const invalidateUsageSummary = useInvalidateUsageSummary()
  return $api.useMutation("post", "/api/usage/models", {
    onSuccess: invalidateUsageSummary,
  })
}

export function useUpdateLlmModelMutation() {
  const invalidateUsageSummary = useInvalidateUsageSummary()
  return $api.useMutation("patch", "/api/usage/models/{model_id}", {
    onSuccess: invalidateUsageSummary,
  })
}

export function useActivateLlmModelMutation() {
  const invalidateUsageSummary = useInvalidateUsageSummary()
  return $api.useMutation("post", "/api/usage/models/{model_id}/activate", {
    onSuccess: invalidateUsageSummary,
  })
}

export function useDeleteLlmModelMutation() {
  const invalidateUsageSummary = useInvalidateUsageSummary()
  return $api.useMutation("delete", "/api/usage/models/{model_id}", {
    onSuccess: invalidateUsageSummary,
  })
}
