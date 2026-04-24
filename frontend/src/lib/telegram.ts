import { fetchClient } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type TelegramStatusResponse = components["schemas"]["TelegramStatusOut"]
export type JoinCodeResponse = components["schemas"]["JoinCodeOut"]

function requireData<T>(data: T | undefined): T {
  if (data === undefined || data === null) {
    throw new Error("Request failed")
  }
  return data
}

export async function fetchTelegramStatus(): Promise<TelegramStatusResponse> {
  const { data } = await fetchClient.GET("/api/telegram/status", {})
  return requireData(data)
}

export async function createTelegramJoinCode(): Promise<JoinCodeResponse> {
  const { data } = await fetchClient.POST("/api/telegram/join-code", {})
  return requireData(data)
}
