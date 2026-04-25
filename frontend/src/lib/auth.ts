import type { QueryClient } from "@tanstack/react-query"

const TOKEN_KEY = "taskraptor_auth_token"
export const SESSION_EXPIRED_ERROR = "SESSION_EXPIRED"
export const NOT_FOUND_ERROR = "NOT_FOUND"

export type MeResponse = {
  id: number
  email: string
  first_name: string
  last_name: string
  date_joined: string
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function isAuthError(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.message === SESSION_EXPIRED_ERROR ||
      error.message === "Not authenticated")
  )
}

export function endSession(queryClient?: QueryClient): void {
  clearToken()
  queryClient?.clear()
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

export async function login(email: string, password: string): Promise<{ token: string }> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<{ token: string }>
}

export async function register(email: string, password: string): Promise<{ token: string }> {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<{ token: string }>
}

export async function fetchMe(): Promise<MeResponse> {
  const token = getToken()
  if (!token) {
    throw new Error("Not authenticated")
  }
  const res = await fetch("/api/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    throw new Error("Not authenticated")
  }
  return res.json() as Promise<MeResponse>
}
