import { useQueryClient } from "@tanstack/react-query"

import { $api } from "@/lib/api/client"

function settingsQueryKey() {
  return ["get", "/api/auth/settings"] as const
}

export function useSettingsQuery() {
  return $api.useQuery("get", "/api/auth/settings", {}, { retry: false })
}

export function useUpdateSettingsMutation() {
  const queryClient = useQueryClient()
  return $api.useMutation("patch", "/api/auth/settings", {
    onSuccess() {
      void queryClient.invalidateQueries({ queryKey: settingsQueryKey() })
    },
  })
}
