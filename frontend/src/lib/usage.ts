import type { components } from "@/lib/api/schema"

export type UsageSummary = components["schemas"]["UsageSummaryOut"]
export type UsageSystemQuota = components["schemas"]["UsageSystemQuotaOut"]
export type UsageTotals = components["schemas"]["UsageTotalsOut"]
export type UsageLlmModel = components["schemas"]["UsageLlmModelOut"]
export type UsageModelCreateInput = components["schemas"]["UsageModelCreateIn"]
export type UsageModelUpdateInput = components["schemas"]["UsageModelUpdateIn"]
export type SupportedModelOption = components["schemas"]["SupportedModelOptionOut"]

export function formatTokenCount(value: number | null | undefined): string {
  const safeValue = value ?? 0
  return new Intl.NumberFormat(undefined, {
    notation: safeValue >= 100_000 ? "compact" : "standard",
    maximumFractionDigits: safeValue >= 100_000 ? 1 : 0,
  }).format(safeValue)
}

export function formatUsageDate(iso: string | null | undefined): string {
  if (!iso) return "No reset date"
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return "No reset date"
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

export function getQuotaPercent(quota: number | null | undefined, used: number | null | undefined): number | null {
  if (quota == null || quota <= 0) return null
  return Math.min(Math.max(((used ?? 0) / quota) * 100, 0), 100)
}
