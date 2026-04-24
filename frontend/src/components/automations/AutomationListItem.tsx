import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import type { Automation } from "@/lib/automations"
import { IconPencil, IconTrash } from "@tabler/icons-react"
import { cn } from "@/lib/utils"

interface AutomationListItemProps {
  automation: Automation
  onEdit: (automation: Automation) => void
  onDelete: (automation: Automation) => void
  onToggleActive: (automation: Automation, isActive: boolean) => void
  isUpdating: boolean
  isDeleting: boolean
}

function formatTime(timeString: string): string {
  const [hours = "00", minutes = "00"] = timeString.split(":")
  const hour = Number.parseInt(hours, 10)
  const ampm = hour >= 12 ? "PM" : "AM"
  const displayHour = hour % 12 || 12
  return `${displayHour}:${minutes} ${ampm}`
}

function formatLastRun(lastRunAt: string | null): string {
  if (!lastRunAt) return "Never run"
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
  onEdit,
  onDelete,
  onToggleActive,
  isUpdating,
  isDeleting,
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
          <span className="text-muted-foreground text-xs">
            · Runs at {formatTime(automation.schedule_time)}
          </span>
        </div>
        <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
          {automation.prompt}
        </p>
        <p className="text-muted-foreground mt-1 text-xs">
          Last run: {formatLastRun(automation.last_run_at)}
        </p>
      </div>
      <div className="flex items-center gap-1">
        <Switch
          checked={automation.is_active}
          onCheckedChange={handleToggle}
          disabled={isUpdating || isTogglePending}
          aria-label={automation.is_active ? "Deactivate automation" : "Activate automation"}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Edit automation"
          onClick={() => onEdit(automation)}
          disabled={isUpdating || isDeleting}
        >
          <IconPencil />
          <span className="sr-only">Edit</span>
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Delete automation"
          onClick={() => onDelete(automation)}
          disabled={isDeleting}
          className="text-destructive hover:text-destructive"
        >
          <IconTrash />
          <span className="sr-only">Delete</span>
        </Button>
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
            <Skeleton className="h-6 w-11 rounded-full" />
            <Skeleton className="size-8" />
            <Skeleton className="size-8" />
          </div>
        </div>
      ))}
    </div>
  )
}
