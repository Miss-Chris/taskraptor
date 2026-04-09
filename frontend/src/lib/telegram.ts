import { getToken } from "@/lib/auth"

export type TelegramStatusResponse = {
  connected: boolean
  bot_name: string
}

export type JoinCodeResponse = {
  code: string
  expires_at: string
  bot_name: string
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

export async function fetchTelegramStatus(): Promise<TelegramStatusResponse> {
  const res = await fetch("/api/telegram/status", {
    headers: { ...authHeaders() },
  })
  if (res.status === 401) {
    throw new Error("SESSION_EXPIRED")
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<TelegramStatusResponse>
}

export async function createTelegramJoinCode(): Promise<JoinCodeResponse> {
  const res = await fetch("/api/telegram/join-code", {
    method: "POST",
    headers: { ...authHeaders() },
  })
  if (res.status === 401) {
    throw new Error("SESSION_EXPIRED")
  }
  if (!res.ok) {
    throw new Error(await parseErrorDetail(res))
  }
  return res.json() as Promise<JoinCodeResponse>
}
