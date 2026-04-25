import { useEffect, useMemo, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { IconSettings } from "@tabler/icons-react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { endSession } from "@/lib/auth"
import { useSettingsQuery, useUpdateSettingsMutation } from "@/queries/settings"

const FALLBACK_TIMEZONES = [
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "UTC",
  "Europe/London",
  "Europe/Paris",
  "Asia/Kolkata",
  "Asia/Tokyo",
  "Australia/Sydney",
]

function getSupportedTimezones() {
  const supportedValuesOf = (
    Intl as typeof Intl & {
      supportedValuesOf?: (input: "timeZone") => string[]
    }
  ).supportedValuesOf

  if (typeof supportedValuesOf === "function") {
    return supportedValuesOf("timeZone")
  }

  return FALLBACK_TIMEZONES
}

function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

function SettingsSkeleton() {
  return (
    <div className="grid gap-4">
      {[0, 1].map((index) => (
        <div key={index} className="rounded-lg border border-border bg-card p-4">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="mt-3 h-4 w-full max-w-lg" />
          <Skeleton className="mt-4 h-9 w-full max-w-md" />
        </div>
      ))}
    </div>
  )
}

export function SettingsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const settingsQuery = useSettingsQuery()
  const updateMutation = useUpdateSettingsMutation()
  const [timezoneDraft, setTimezoneDraft] = useState<string | null>(null)
  const [promptInstructionsDraft, setPromptInstructionsDraft] = useState<
    string | null
  >(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  useDocumentTitle("Settings")

  useEffect(() => {
    const err = settingsQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      endSession(queryClient)
      navigate("/login", { replace: true })
    }
  }, [navigate, queryClient, settingsQuery.error])

  const timezone = timezoneDraft ?? settingsQuery.data?.timezone ?? ""
  const savedPromptInstructions =
    settingsQuery.data?.prompt_instructions ?? ""
  const promptInstructions =
    promptInstructionsDraft ?? savedPromptInstructions
  const promptChanged = promptInstructions !== savedPromptInstructions

  const timezoneOptions = useMemo(() => {
    const options = getSupportedTimezones()
    if (timezone && !options.includes(timezone)) {
      return [timezone, ...options]
    }
    return options
  }, [timezone])

  async function handleTimezoneChange(
    event: React.ChangeEvent<HTMLSelectElement>
  ) {
    const nextTimezone = event.target.value
    setTimezoneDraft(nextTimezone)
    setActionError(null)
    setStatusMessage(null)

    try {
      await updateMutation.mutateAsync({
        body: { timezone: nextTimezone },
      })
      setTimezoneDraft(null)
      setStatusMessage("Timezone saved.")
    } catch (err) {
      setActionError(getErrorMessage(err, "Failed to save timezone."))
      setTimezoneDraft(null)
    }
  }

  async function handleSavePromptInstructions(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault()
    setActionError(null)
    setStatusMessage(null)

    try {
      await updateMutation.mutateAsync({
        body: { prompt_instructions: promptInstructions },
      })
      setPromptInstructionsDraft(null)
      setStatusMessage("Prompt instructions saved.")
    } catch (err) {
      setActionError(
        getErrorMessage(err, "Failed to save prompt instructions.")
      )
    }
  }

  return (
    <div className="flex w-full max-w-none flex-1 flex-col gap-5">
      <header className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage your timezone and the instructions TaskRaptor should keep in
            mind.
          </p>
        </div>
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
          <IconSettings className="size-5 text-muted-foreground" />
        </div>
      </header>

      {settingsQuery.isLoading ? (
        <SettingsSkeleton />
      ) : settingsQuery.isError ? (
        <p className="text-sm text-destructive">Could not load settings.</p>
      ) : (
        <div className="grid gap-4">
          <section className="rounded-lg border border-border bg-card p-4">
            <div className="max-w-2xl">
              <h2 className="text-sm font-semibold">Timezone</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Used when TaskRaptor schedules automations and interprets dates.
              </p>
              <div className="mt-4 grid gap-2">
                <Label htmlFor="timezone">Timezone</Label>
                <select
                  id="timezone"
                  value={timezone}
                  onChange={handleTimezoneChange}
                  className="h-9 w-full max-w-md rounded-3xl border border-input bg-input/50 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={updateMutation.isPending}
                >
                  {timezoneOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <form
              className="max-w-2xl"
              onSubmit={handleSavePromptInstructions}
            >
              <h2 className="text-sm font-semibold">
                Custom prompt instructions
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Add standing context or preferences that should guide future
                agent conversations.
              </p>
              <div className="mt-4 grid gap-2">
                <Label htmlFor="prompt-instructions">Instructions</Label>
                <Textarea
                  id="prompt-instructions"
                  value={promptInstructions}
                  onChange={(event) =>
                    setPromptInstructionsDraft(event.target.value)
                  }
                  placeholder="Example: Prefer concise answers and always ask before changing production configuration."
                  className="min-h-40"
                  disabled={updateMutation.isPending}
                />
              </div>
              {promptChanged ? (
                <div className="mt-4">
                  <Button type="submit" disabled={updateMutation.isPending}>
                    {updateMutation.isPending ? "Saving..." : "Save"}
                  </Button>
                </div>
              ) : null}
            </form>
          </section>

          {actionError ? (
            <p className="text-sm text-destructive" role="alert">
              {actionError}
            </p>
          ) : null}
          {statusMessage ? (
            <p className="text-sm text-muted-foreground" role="status">
              {statusMessage}
            </p>
          ) : null}
        </div>
      )}
    </div>
  )
}
