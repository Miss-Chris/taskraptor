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
import { timezoneOptionsWithSelected } from "@/lib/timezones"
import { useSettingsQuery, useUpdateSettingsMutation } from "@/queries/settings"

function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

const personaOptions = [
  {
    value: "helpful",
    label: "Helpful",
    description:
      "Professional and friendly. Keeps replies concise and list-oriented.",
  },
  {
    value: "encouraging",
    label: "Encouraging",
    description: "Warmer and more upbeat while still keeping replies concise.",
  },
  {
    value: "minimal",
    label: "Minimal",
    description: "Dry, terse, and strictly functional.",
  },
  {
    value: "custom",
    label: "Custom",
    description: "Use your own tone instructions for future chats.",
  },
] as const

function SettingsSkeleton() {
  return (
    <div className="grid gap-4">
      {[0, 1, 2].map((index) => (
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
  const [personaDraft, setPersonaDraft] = useState<string | null>(null)
  const [customPersonaDraft, setCustomPersonaDraft] = useState<string | null>(
    null
  )
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

  const savedTimezone = settingsQuery.data?.timezone ?? ""
  const timezone = timezoneDraft ?? savedTimezone
  const savedPromptInstructions =
    settingsQuery.data?.prompt_instructions ?? ""
  const promptInstructions =
    promptInstructionsDraft ?? savedPromptInstructions
  const savedPersona = settingsQuery.data?.persona ?? "helpful"
  const persona = personaDraft ?? savedPersona
  const savedCustomPersona = settingsQuery.data?.custom_persona ?? ""
  const customPersona = customPersonaDraft ?? savedCustomPersona
  const timezoneChanged = timezone !== savedTimezone
  const promptChanged = promptInstructions !== savedPromptInstructions
  const personaChanged =
    persona !== savedPersona || customPersona !== savedCustomPersona

  const timezoneOptions = useMemo(() => {
    return timezoneOptionsWithSelected(timezone || null)
  }, [timezone])

  async function handleSaveTimezone(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setActionError(null)
    setStatusMessage(null)

    try {
      await updateMutation.mutateAsync({
        body: { timezone },
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

  async function handleSavePersona(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setActionError(null)
    setStatusMessage(null)

    try {
      await updateMutation.mutateAsync({
        body: { persona, custom_persona: customPersona },
      })
      setPersonaDraft(null)
      setCustomPersonaDraft(null)
      setStatusMessage("Persona saved.")
    } catch (err) {
      setActionError(getErrorMessage(err, "Failed to save persona."))
    }
  }

  return (
    <div className="flex w-full max-w-none flex-1 flex-col gap-5">
      <header className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-page-title">Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage your timezone, chat persona, and the instructions TaskRaptor
            should keep in mind.
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
            <form className="max-w-2xl" onSubmit={handleSaveTimezone}>
              <h2 className="text-section-title">Timezone</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Used when TaskRaptor schedules automations and interprets dates.
              </p>
              <div className="mt-4 grid gap-2">
                <Label htmlFor="timezone">Timezone</Label>
                <select
                  id="timezone"
                  value={timezone}
                  onChange={(event) => {
                    setTimezoneDraft(event.target.value)
                    setActionError(null)
                    setStatusMessage(null)
                  }}
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
              <div className="mt-4">
                <Button
                  type="submit"
                  disabled={
                    updateMutation.isPending || !timezone || !timezoneChanged
                  }
                >
                  {updateMutation.isPending ? "Saving..." : "Save"}
                </Button>
              </div>
            </form>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <form className="max-w-2xl" onSubmit={handleSavePersona}>
              <h2 className="text-section-title">Chat persona</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Choose how TaskRaptor should sound in future chats.
              </p>
              <div className="mt-4 grid gap-2">
                <Label htmlFor="persona">Persona</Label>
                <select
                  id="persona"
                  value={persona}
                  onChange={(event) => {
                    setPersonaDraft(event.target.value)
                    setActionError(null)
                    setStatusMessage(null)
                  }}
                  className="h-9 w-full max-w-md rounded-3xl border border-input bg-input/50 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={updateMutation.isPending}
                >
                  {personaOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="text-sm text-muted-foreground">
                  {
                    personaOptions.find((option) => option.value === persona)
                      ?.description
                  }
                </p>
              </div>
              {persona === "custom" ? (
                <div className="mt-4 grid gap-2">
                  <Label htmlFor="custom-persona">Custom tone</Label>
                  <Textarea
                    id="custom-persona"
                    value={customPersona}
                    onChange={(event) =>
                      setCustomPersonaDraft(event.target.value)
                    }
                    placeholder="Example: Use clipped sentences and avoid upbeat phrasing."
                    className="min-h-32"
                    disabled={updateMutation.isPending}
                  />
                </div>
              ) : null}
              {personaChanged ? (
                <div className="mt-4">
                  <Button
                    type="submit"
                    disabled={
                      updateMutation.isPending ||
                      (persona === "custom" && !customPersona.trim())
                    }
                  >
                    {updateMutation.isPending ? "Saving..." : "Save"}
                  </Button>
                </div>
              ) : null}
            </form>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <form
              className="max-w-2xl"
              onSubmit={handleSavePromptInstructions}
            >
              <h2 className="text-section-title">
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
