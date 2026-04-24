import { type FormEvent, useState } from "react"

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import type { Automation, AutomationCreateInput, AutomationUpdateInput } from "@/lib/automations"
import { normalizeScheduleTime } from "@/lib/automations"

export interface AutomationDialogProps {
  automation: Automation | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: AutomationCreateInput | AutomationUpdateInput) => Promise<void>
  isSubmitting: boolean
}

interface AutomationFormContentProps {
  automation: Automation | null
  onSubmit: (data: AutomationCreateInput | AutomationUpdateInput) => Promise<void>
  onCancel: () => void
  isSubmitting: boolean
}

function AutomationFormContent({
  automation,
  onSubmit,
  onCancel,
  isSubmitting,
}: AutomationFormContentProps) {
  const isEditMode = automation != null
  const initialPrompt = automation?.prompt ?? ""
  const initialScheduleTime = automation?.schedule_time.slice(0, 5) ?? ""
  const initialIsActive = automation?.is_active ?? true

  const [prompt, setPrompt] = useState(initialPrompt)
  const [scheduleTime, setScheduleTime] = useState(initialScheduleTime)
  const [isActive, setIsActive] = useState(initialIsActive)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    const trimmedPrompt = prompt.trim()
    if (!trimmedPrompt) {
      setError("Prompt is required")
      return
    }
    if (!scheduleTime) {
      setError("Schedule time is required")
      return
    }

    const normalizedTime = normalizeScheduleTime(scheduleTime)

    try {
      if (isEditMode && automation) {
        const updateData: AutomationUpdateInput = {
          prompt: trimmedPrompt,
          schedule_time: normalizedTime,
          is_active: isActive,
        }
        await onSubmit(updateData)
      } else {
        const createData: AutomationCreateInput = {
          prompt: trimmedPrompt,
          schedule_time: normalizedTime,
        }
        await onSubmit(createData)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong")
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="grid gap-4 py-4">
        {error ? (
          <p className="text-destructive text-sm" role="alert">
            {error}
          </p>
        ) : null}
        <div className="grid gap-2">
          <Label htmlFor="automation-prompt">Prompt</Label>
          <textarea
            id="automation-prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Enter the prompt or instruction for this automation..."
            required
            minLength={1}
            rows={4}
            className="min-h-[80px] w-full rounded-3xl border border-transparent bg-input/50 px-3 py-2 text-base transition-[color,box-shadow,background-color] outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40"
          />
          <p className="text-muted-foreground text-xs">
            This markdown will be sent as the system message when the automation runs.
          </p>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="automation-time">Schedule time</Label>
          <Input
            id="automation-time"
            type="time"
            step="60"
            value={scheduleTime}
            onChange={(e) => setScheduleTime(e.target.value)}
            required
          />
          <p className="text-muted-foreground text-xs">
            The time (in your local timezone) when this automation will run daily.
          </p>
        </div>
        {isEditMode && (
          <div className="flex items-center justify-between">
            <Label htmlFor="automation-active" className="cursor-pointer">
              Active
            </Label>
            <Switch
              id="automation-active"
              checked={isActive}
              onCheckedChange={setIsActive}
            />
          </div>
        )}
      </div>
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline" disabled={isSubmitting} onClick={onCancel}>
            Cancel
          </Button>
        </DialogClose>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? isEditMode
              ? "Saving..."
              : "Creating..."
            : isEditMode
              ? "Save changes"
              : "Create automation"}
        </Button>
      </DialogFooter>
    </form>
  )
}

export function AutomationDialog({
  automation,
  open,
  onOpenChange,
  onSubmit,
  isSubmitting,
}: AutomationDialogProps) {
  const isEditMode = automation != null
  const dialogKey = automation?.id ?? "create"

  async function handleSubmit(data: AutomationCreateInput | AutomationUpdateInput) {
    await onSubmit(data)
    onOpenChange(false)
  }

  function handleCancel() {
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEditMode ? "Edit automation" : "New automation"}</DialogTitle>
          <DialogDescription>
            {isEditMode
              ? "Update your scheduled automation details."
              : "Create a new automation that runs at a scheduled time each day."}
          </DialogDescription>
        </DialogHeader>
        <AutomationFormContent
          key={dialogKey}
          automation={automation}
          onSubmit={handleSubmit}
          onCancel={handleCancel}
          isSubmitting={isSubmitting}
        />
      </DialogContent>
    </Dialog>
  )
}
