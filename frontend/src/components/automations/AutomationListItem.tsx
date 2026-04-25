import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import type { Automation } from "@/lib/automations"
import { IconDots, IconPencil, IconPlayerPlay, IconTrash } from "@tabler/icons-react"
import { cn } from "@/lib/utils"

interface AutomationListItemProps {
  automation: Automation
  onTest: (automation: Automation) => void
  onEdit: (automation: Automation) => void
  onDelete: (automation: Automation) => void
  onToggleActive: (automation: Automation, isActive: boolean) => void
  isTesting: boolean
  isUpdating: boolean
  isDeleting: boolean
  testResult?: { queued: boolean } | { error: string } | null
}

function formatUtcTime(timeString: string): string {
  const [hours = "00", minutes = "00"] = timeString.split(":")
  const hour = Number.parseInt(hours, 10)
  const ampm = hour >= 12 ? "PM" : "AM"
  const displayHour = hour % 12 || 12
  return `${displayHour}:${minutes} ${ampm} UTC`
}

function utcTimeToLocal(timeString: string): string {
  const [hours = "00", minutes = "00"] = timeString.split(":")
  const now = new Date()
  const utcDate = new Date(
    Date.UTC(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      Number.parseInt(hours, 10),
      Number.parseInt(minutes, 10)
    )
  )
  return utcDate.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  })
}

function formatLastRun(lastRunAt: string | null): string {
  if (!lastRunAt) return "Never"
  const date = new Date(lastRunAt)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    if (diffHours === 0) {
      const diffMinutes = Math.floor(diffMs / (1000 * 60))
      return diffMinutes === 0 ? "Just now" : `${diffMinutes}m ago`
    }
    return `${diffHours}h ago`
  }
  if (diffDays === 1) return "Yesterday"
  if (diffDays < 7) return `${diffDays} days ago`
  return date.toLocaleDateString()
}

export function AutomationListItem({
  automation,
  onTest,
  onEdit,
  onDelete,
  onToggleActive,
  isTesting,
  isUpdating,
  isDeleting,
  testResult,
}: AutomationListItemProps) {
  const [isTogglePending, setIsTogglePending] = useState(false)

  async function handleToggle(checked: boolean) {
    setIsTogglePending(true)
    try {
      await onToggleActive(automation, checked)
    } finally {
      setIsTogglePending(false)
    }
  }

  const utcTime = formatUtcTime(automation.schedule_time)
  const localTime = utcTimeToLocal(automation.schedule_time)
  const showLocalTime = localTime !== utcTime

  return (
    <div
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 p-3 sm:p-4",
        "border-b border-border last:border-b-0"
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "size-2 rounded-full",
              automation.is_active ? "bg-emerald-400" : "bg-muted-foreground"
            )}
          />
          <span className="text-sm font-medium">
            {automation.is_active ? "Active" : "Inactive"}
          </span>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-muted-foreground cursor-default text-xs underline decoration-dotted underline-offset-2">
                  · Runs at {utcTime}
                </span>
              </TooltipTrigger>
              {showLocalTime && (
                <TooltipContent>
                  {localTime} in your timezone
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        </div>
        <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
          {automation.prompt}
        </p>
        <div className="mt-1 flex items-center gap-2">
          <p className="text-muted-foreground text-xs">
            Last run: {formatLastRun(automation.last_run_at)}
          </p>
          {testResult != null && (
            <span
              className={cn(
                "inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-medium",
                "error" in testResult
                  ? "bg-destructive/10 text-destructive"
                  : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
              )}
            >
              {"error" in testResult ? testResult.error : "Test queued"}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label="Test automation"
          onClick={() => onTest(automation)}
          disabled={isTesting}
        >
          <IconPlayerPlay />
          {isTesting ? "Testing..." : "Test"}
        </Button>
        <Switch
          checked={automation.is_active}
          onCheckedChange={handleToggle}
          disabled={isUpdating || isTogglePending}
          aria-label={automation.is_active ? "Deactivate automation" : "Activate automation"}
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="More options"
              disabled={isUpdating || isDeleting}
            >
              <IconDots />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onEdit(automation)}>
              <IconPencil className="size-4" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => onDelete(automation)}
              className="text-destructive focus:text-destructive"
            >
              <IconTrash className="size-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}

interface AutomationListSkeletonProps {
  count?: number
}

export function AutomationListSkeleton({ count = 3 }: AutomationListSkeletonProps) {
  return (
    <div className="divide-y divide-border rounded-lg border border-border">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 p-3 sm:p-4">
          <div className="min-w-0 space-y-2">
            <div className="flex items-center gap-2">
              <Skeleton className="size-2 rounded-full" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-3 w-24" />
            </div>
            <Skeleton className="h-4 w-full max-w-[300px]" />
            <Skeleton className="h-3 w-24" />
          </div>
          <div className="flex items-center gap-1">
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-6 w-11 rounded-full" />
            <Skeleton className="size-8" />
          </div>
        </div>
      ))}
    </div>
  )
}
