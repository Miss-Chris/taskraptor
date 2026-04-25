import type { ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { Navigate, useLocation } from "react-router-dom"

import { fetchMe, getToken } from "@/lib/auth"

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation()
  const token = getToken()
  const meQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: fetchMe,
    enabled: Boolean(token),
    retry: false,
    staleTime: 60_000,
  })

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (meQuery.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <p className="text-sm text-muted-foreground">Checking session...</p>
      </div>
    )
  }

  if (meQuery.isError) {
    return null
  }

  return <>{children}</>
}
