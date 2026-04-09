import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"

import { getToken } from "@/lib/auth"

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation()
  const token = getToken()
  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}
