import { cn } from "@/lib/utils"
import { formatTokenCount, getQuotaPercent } from "@/lib/usage"

type UsageMeterProps = {
  quota: number | null
  quotaUsed: number
  quotaRemaining: number | null
  isAvailable: boolean
  unitSingular?: string
  unitPlural?: string
  compact?: boolean
  /** Show "X / Y units used" format instead of "X of Y units · N left" */
  usedFormat?: boolean
  className?: string
}

export function UsageMeter({
  quota,
  quotaUsed,
  quotaRemaining,
  isAvailable,
  unitSingular = "token",
  unitPlural = "tokens",
  compact = false,
  usedFormat = false,
  className,
}: UsageMeterProps) {
  const percent = getQuotaPercent(quota, quotaUsed)
  const unlimited = quota == null
  const exhausted = !unlimited && (quotaRemaining ?? 0) <= 0
  const unitFor = (value: number | null | undefined) => (value === 1 ? unitSingular : unitPlural)

  const label = usedFormat
    ? unlimited
      ? `${formatTokenCount(quotaUsed)} ${unitFor(quotaUsed)} used`
      : `${formatTokenCount(quotaUsed)} / ${formatTokenCount(quota)} ${unitFor(quota)} used`
    : unlimited
      ? `${formatTokenCount(quotaUsed)} ${unitFor(quotaUsed)} used`
      : `${formatTokenCount(quotaUsed)} of ${formatTokenCount(quota)} ${unitFor(quota)}`

  const secondaryLabel = unlimited
    ? "Unlimited"
    : exhausted
      ? "Exhausted"
      : `${formatTokenCount(quotaRemaining)} ${unitFor(quotaRemaining)} left`

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className={cn("min-w-0 truncate", compact ? "text-sidebar-foreground" : "font-medium")}>{label}</span>
        {!usedFormat && (
          <span
            className={cn(
              "shrink-0",
              !isAvailable || exhausted ? "text-destructive" : "text-muted-foreground",
            )}
          >
            {!isAvailable ? "Unavailable" : secondaryLabel}
          </span>
        )}
        {usedFormat && (!isAvailable || exhausted) && (
          <span className="shrink-0 text-destructive">
            {!isAvailable ? "Unavailable" : "Exhausted"}
          </span>
        )}
      </div>
      <div className={cn("h-2 overflow-hidden rounded-full bg-muted", compact && "h-1.5 bg-sidebar-accent")}>
        <div
          className={cn(
            "h-full rounded-full transition-all",
            !isAvailable || exhausted ? "bg-destructive" : "bg-primary",
            unlimited && "w-full opacity-35",
          )}
          style={unlimited ? undefined : { width: `${percent ?? 0}%` }}
        />
      </div>
    </div>
  )
}
