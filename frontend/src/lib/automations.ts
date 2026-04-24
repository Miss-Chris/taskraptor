import { fetchClient } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

export type Automation = components["schemas"]["AutomationOut"]
export type AutomationListResponse = components["schemas"]["AutomationListOut"]
export type AutomationCreateInput = components["schemas"]["AutomationCreateIn"]
export type AutomationUpdateInput = components["schemas"]["AutomationUpdateIn"]

function requireData<T>(data: T | undefined): T {
  if (data === undefined || data === null) {
    throw new Error("Request failed")
  }
  return data
}

export function normalizeScheduleTime(value: string): string {
  const trimmed = value.trim()
  if (/^\d{2}:\d{2}$/.test(trimmed)) {
    return `${trimmed}:00`
  }
  return trimmed
}

export async function fetchAutomations(): Promise<AutomationListResponse> {
  const { data } = await fetchClient.GET("/api/automations/", {})
  return requireData(data)
}

export async function fetchAutomation(
  automationId: string
): Promise<Automation> {
  const { data } = await fetchClient.GET(
    "/api/automations/{automation_id}",
    {
      params: { path: { automation_id: automationId } },
    }
  )
  return requireData(data)
}
