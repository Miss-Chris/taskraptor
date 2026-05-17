import { useEffect, useMemo, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import {
  IconCheck,
  IconCpu,
  IconKey,
  IconPlus,
  IconSettings,
  IconTrash,
} from "@tabler/icons-react"

import { UsageMeter } from "@/components/usage/UsageMeter"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { endSession } from "@/lib/auth"
import { cn } from "@/lib/utils"
import {
  formatTokenCount,
  formatUsageDate,
  type SupportedModelOption,
  type UsageLlmModel,
  type UsageModelCreateInput,
  type UsageModelUpdateInput,
} from "@/lib/usage"
import {
  useActivateLlmModelMutation,
  useCreateLlmModelMutation,
  useDeleteLlmModelMutation,
  useUpdateLlmModelMutation,
  useUsageSummaryQuery,
} from "@/queries/usage"

const DEFAULT_CONTEXT_LIMIT = 25

const INCLUDED_MODEL_DESCRIPTION =
  "50 requests per month, free. No API key needed. Good for trying things out and light daily use. Connect your own Anthropic, DeepSeek, or OpenAI key for unlimited use."

/** Produce a human-readable model name from the backend display_name. */
function humanizeDisplayName(displayName: string, provider: string): string {
  // Remove trailing 8-digit date stamps like "20251001"
  let name = displayName.replace(/\s+\d{8}$/, "").trim()
  // Collapse adjacent digit tokens: "4 5" → "4.5"
  name = name.replace(/\b(\d+)\s+(\d+)\b/g, "$1.$2")
  // Strip leading provider prefix (case-insensitive) before title-casing
  const providerNorm = provider === "system_free" ? "system" : provider
  name = name.replace(new RegExp(`^${providerNorm}\\s+`, "i"), "")
  // Title-case
  name = name.replace(/\b\w/g, (c) => c.toUpperCase())
  return name
}

function sourceLabel(model: UsageLlmModel): string {
  return model.is_system ? "Included" : "Your API key"
}

function resetDateText(model: UsageLlmModel): string {
  if (!model.quota_expires_at) return "No reset date set."
  return `Resets ${formatUsageDate(model.quota_expires_at)}.`
}

function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

function StatusPill({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode
  tone?: "neutral" | "success" | "danger"
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        tone === "success" &&
          "border-emerald-500/30 bg-emerald-500/10 text-emerald-700",
        tone === "danger" &&
          "border-destructive/30 bg-destructive/10 text-destructive",
        tone === "neutral" && "border-border bg-muted text-muted-foreground"
      )}
    >
      {children}
    </span>
  )
}

type ModelDialogState =
  | { mode: "create"; model: null }
  | { mode: "edit"; model: UsageLlmModel }

function ModelDialog({
  state,
  supportedModels,
  open,
  onOpenChange,
  onSubmit,
  isSubmitting,
}: {
  state: ModelDialogState
  supportedModels: SupportedModelOption[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (
    data: UsageModelCreateInput | UsageModelUpdateInput
  ) => Promise<void>
  isSubmitting: boolean
}) {
  const firstOption = supportedModels[0]?.model_key ?? ""
  const isEdit = state.mode === "edit"
  const [modelKey, setModelKey] = useState(
    isEdit ? state.model.model_key : firstOption
  )
  const [apiKey, setApiKey] = useState("")
  const [contextLimit, setContextLimit] = useState(
    isEdit
      ? String(state.model.context_message_limit)
      : String(DEFAULT_CONTEXT_LIMIT)
  )
  const [activate, setActivate] = useState(
    isEdit ? state.model.is_active : true
  )
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    const parsedContextLimit = Number(contextLimit)
    if (
      !Number.isInteger(parsedContextLimit) ||
      parsedContextLimit < 1 ||
      parsedContextLimit > 1024
    ) {
      setError("Context message limit must be between 1 and 1024.")
      return
    }
    if (!isEdit && !apiKey.trim()) {
      setError("API key is required.")
      return
    }
    if (!isEdit && !modelKey) {
      setError("Choose a model.")
      return
    }

    try {
      if (isEdit) {
        const body: UsageModelUpdateInput = {
          context_message_limit: parsedContextLimit,
        }
        if (apiKey.trim()) body.api_key = apiKey.trim()
        await onSubmit(body)
      } else {
        await onSubmit({
          model_key: modelKey,
          api_key: apiKey.trim(),
          context_message_limit: parsedContextLimit,
          is_active: activate,
        })
      }
      onOpenChange(false)
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          isEdit ? "Failed to update model" : "Failed to add provider key"
        )
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit} className="contents">
          <DialogHeader>
            <DialogTitle>
              {isEdit ? "Edit provider key" : "Add provider key"}
            </DialogTitle>
            <DialogDescription>
              {isEdit
                ? "Update the API key or context limit for this model."
                : "Connect your own Anthropic, DeepSeek, or OpenAI API key."}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="model-key">Model</Label>
              {isEdit ? (
                <Input
                  id="model-key"
                  value={humanizeDisplayName(
                    state.model.display_name,
                    state.model.provider
                  )}
                  disabled
                />
              ) : (
                <select
                  id="model-key"
                  value={modelKey}
                  onChange={(event) => setModelKey(event.target.value)}
                  className="h-9 w-full rounded-3xl border border-input bg-input/50 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
                  disabled={supportedModels.length === 0}
                >
                  {supportedModels.map((option) => (
                    <option key={option.model_key} value={option.model_key}>
                      {humanizeDisplayName(option.display_name, option.provider)}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="api-key">API key</Label>
              <Input
                id="api-key"
                type="password"
                value={apiKey}
                placeholder={
                  isEdit
                    ? "Leave blank to keep the current key"
                    : "Provider API key"
                }
                onChange={(event) => setApiKey(event.target.value)}
                autoComplete="off"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="context-limit">Context message limit</Label>
              <Input
                id="context-limit"
                type="number"
                min={1}
                max={1024}
                value={contextLimit}
                onChange={(event) => setContextLimit(event.target.value)}
              />
            </div>

            {!isEdit ? (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-border p-3">
                <div>
                  <Label htmlFor="activate-model">Activate immediately</Label>
                  <p className="mt-1 text-xs text-muted-foreground">
                    This will become the model used by chats.
                  </p>
                </div>
                <Switch
                  id="activate-model"
                  checked={activate}
                  onCheckedChange={setActivate}
                />
              </div>
            ) : null}

            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={isSubmitting}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              type="submit"
              disabled={
                isSubmitting || (!isEdit && supportedModels.length === 0)
              }
            >
              {isSubmitting ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function CurrentlyUsingCard({ model }: { model: UsageLlmModel }) {
  const name = humanizeDisplayName(model.display_name, model.provider)

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Currently using
      </p>
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
          {model.is_system ? (
            <IconCpu className="size-5 text-muted-foreground" />
          ) : (
            <IconKey className="size-5 text-muted-foreground" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-section-title">{name}</h2>
            <StatusPill tone="success">Active</StatusPill>
            {model.supports_image_input && (
              <StatusPill tone="neutral">Images</StatusPill>
            )}
            {!model.is_available && (
              <StatusPill tone="danger">Unavailable</StatusPill>
            )}
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {sourceLabel(model)}&nbsp;·&nbsp;
            <span className="font-mono">{model.model_key}</span>
          </p>

          {model.is_system ? (
            <div className="mt-4">
              <UsageMeter
                quota={model.quota}
                quotaUsed={model.quota_used}
                quotaRemaining={model.quota_remaining}
                isAvailable={model.is_available}
                unitSingular="request"
                unitPlural="requests"
                usedFormat
              />
              <p className="mt-1.5 text-xs text-muted-foreground">
                {resetDateText(model)}
              </p>
              <p className="mt-3 text-xs text-muted-foreground">
                {INCLUDED_MODEL_DESCRIPTION}
              </p>
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">
              Tokens used:{" "}
              <span className="font-medium text-foreground">
                {formatTokenCount(model.quota_used)}
              </span>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function ModelListItem({
  model,
  onActivate,
  onEdit,
  onDelete,
  isMutating,
}: {
  model: UsageLlmModel
  onActivate: (model: UsageLlmModel) => void
  onEdit: (model: UsageLlmModel) => void
  onDelete: (model: UsageLlmModel) => void
  isMutating: boolean
}) {
  const name = humanizeDisplayName(model.display_name, model.provider)
  const canDelete = !model.is_system && !model.is_active

  return (
    <div className="flex items-start gap-3 p-4">
      {/* Radio indicator */}
      <div
        className={cn(
          "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
          model.is_active
            ? "border-primary"
            : "border-muted-foreground/40"
        )}
      >
        {model.is_active && (
          <div className="size-2 rounded-full bg-primary" />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{name}</span>
              <StatusPill tone="neutral">{sourceLabel(model)}</StatusPill>
              {model.supports_image_input && (
                <StatusPill tone="neutral">Images</StatusPill>
              )}
              {model.is_active && !model.is_available && (
                <StatusPill tone="danger">Unavailable</StatusPill>
              )}
            </div>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">
              {model.model_key}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {!model.is_active && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onActivate(model)}
                disabled={isMutating}
              >
                <IconCheck />
                Activate
              </Button>
            )}
            {!model.is_system && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onEdit(model)}
                disabled={isMutating}
              >
                <IconSettings />
                Edit
              </Button>
            )}
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={() => onDelete(model)}
              disabled={model.is_system || !canDelete || isMutating}
              title={
                model.is_active && !model.is_system
                  ? "Activate another model before removing this one."
                  : undefined
              }
            >
              <IconTrash />
              Remove
            </Button>
          </div>
        </div>

        <div className="mt-2.5">
          {model.is_system ? (
            <UsageMeter
              quota={model.quota}
              quotaUsed={model.quota_used}
              quotaRemaining={model.quota_remaining}
              isAvailable={model.is_active ? model.is_available : true}
              unitSingular="request"
              unitPlural="requests"
              usedFormat
              compact
            />
          ) : (
            <p className="text-xs text-muted-foreground">
              Tokens used:{" "}
              <span className="font-medium text-foreground">
                {formatTokenCount(model.quota_used)}
              </span>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function CurrentlyUsingCardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <Skeleton className="mb-3 h-3 w-24" />
      <div className="flex items-start gap-3">
        <Skeleton className="size-10 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3 w-64" />
          <div className="mt-4 space-y-2">
            <Skeleton className="h-3 w-full max-w-xs" />
            <Skeleton className="h-2 w-full max-w-xs" />
          </div>
        </div>
      </div>
    </div>
  )
}

function ModelListSkeleton() {
  return (
    <div className="divide-y divide-border rounded-lg border border-border">
      {[0, 1].map((index) => (
        <div key={index} className="flex items-start gap-3 p-4">
          <Skeleton className="mt-0.5 size-4 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-56" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function ModelsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const usageQuery = useUsageSummaryQuery()
  const createMutation = useCreateLlmModelMutation()
  const updateMutation = useUpdateLlmModelMutation()
  const activateMutation = useActivateLlmModelMutation()
  const deleteMutation = useDeleteLlmModelMutation()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogState, setDialogState] = useState<ModelDialogState>({
    mode: "create",
    model: null,
  })
  const [deleteTarget, setDeleteTarget] = useState<UsageLlmModel | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useDocumentTitle("Models")

  useEffect(() => {
    const err = usageQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      endSession(queryClient)
      navigate("/login", { replace: true })
    }
  }, [navigate, queryClient, usageQuery.error])

  const summary = usageQuery.data
  const models = useMemo(() => summary?.models ?? [], [summary?.models])
  const activeModel = useMemo(
    () => models.find((model) => model.is_active) ?? null,
    [models]
  )
  const isMutating =
    createMutation.isPending ||
    updateMutation.isPending ||
    activateMutation.isPending ||
    deleteMutation.isPending

  function handleNewModel() {
    setDialogState({ mode: "create", model: null })
    setDialogOpen(true)
  }

  function handleEditModel(model: UsageLlmModel) {
    setDialogState({ mode: "edit", model })
    setDialogOpen(true)
  }

  async function handleSubmitModel(
    data: UsageModelCreateInput | UsageModelUpdateInput
  ) {
    if (dialogState.mode === "edit") {
      await updateMutation.mutateAsync({
        params: { path: { model_id: dialogState.model.id } },
        body: data as UsageModelUpdateInput,
      })
    } else {
      await createMutation.mutateAsync({
        body: data as UsageModelCreateInput,
      })
    }
  }

  async function handleActivateModel(model: UsageLlmModel) {
    setActionError(null)
    try {
      await activateMutation.mutateAsync({
        params: { path: { model_id: model.id } },
      })
    } catch (err) {
      setActionError(getErrorMessage(err, "Failed to activate model"))
    }
  }

  function handleDeleteClick(model: UsageLlmModel) {
    setDeleteTarget(model)
    setDeleteError(null)
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return
    setDeleteError(null)
    try {
      await deleteMutation.mutateAsync({
        params: { path: { model_id: deleteTarget.id } },
      })
      setDeleteTarget(null)
    } catch (err) {
      setDeleteError(getErrorMessage(err, "Failed to remove model"))
    }
  }

  return (
    <div className="flex w-full max-w-none flex-1 flex-col gap-5">
      <header className="border-b border-border pb-4">
        <h1 className="text-page-title">Models</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {usageQuery.isLoading
            ? "Loading model settings..."
            : activeModel
              ? `Using ${humanizeDisplayName(activeModel.display_name, activeModel.provider)}.`
              : "No active model found."}
        </p>
      </header>

      {usageQuery.isError ? (
        <p className="text-sm text-destructive">Could not load model usage.</p>
      ) : (
        <>
          {usageQuery.isLoading ? (
            <CurrentlyUsingCardSkeleton />
          ) : activeModel ? (
            <CurrentlyUsingCard model={activeModel} />
          ) : null}

          {actionError ? (
            <p className="text-sm text-destructive" role="alert">
              {actionError}
            </p>
          ) : null}

          <section>
            <h2 className="mb-3 text-section-title">Available models</h2>
            {usageQuery.isLoading ? (
              <ModelListSkeleton />
            ) : models.length > 0 ? (
              <div className="divide-y divide-border rounded-lg border border-border">
                {models.map((model) => (
                  <ModelListItem
                    key={model.id}
                    model={model}
                    onActivate={handleActivateModel}
                    onEdit={handleEditModel}
                    onDelete={handleDeleteClick}
                    isMutating={isMutating}
                  />
                ))}
                <div className="p-4">
                  <button
                    type="button"
                    onClick={handleNewModel}
                    disabled={usageQuery.isLoading}
                    className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
                  >
                    <IconPlus className="size-4" />
                    Add a provider key
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[18rem] flex-col items-center justify-center gap-4 rounded-lg border border-border text-center">
                <div className="flex size-12 items-center justify-center rounded-full bg-muted">
                  <IconCpu className="size-6 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium">No models available</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Add a provider key to start using TaskRaptor.
                  </p>
                </div>
                <Button type="button" onClick={handleNewModel}>
                  <IconPlus />
                  Add a provider key
                </Button>
              </div>
            )}
          </section>
        </>
      )}

      <ModelDialog
        key={`${dialogOpen}-${dialogState.mode}-${dialogState.model?.id ?? "new"}-${summary?.supported_models[0]?.model_key ?? "none"}`}
        state={dialogState}
        supportedModels={summary?.supported_models ?? []}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmit={handleSubmitModel}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
      />

      <Dialog
        open={deleteTarget != null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null)
            setDeleteError(null)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove model?</DialogTitle>
            <DialogDescription>
              This removes the saved API key and model settings.
              {deleteTarget ? (
                <span className="mt-2 block font-medium text-foreground">
                  {humanizeDisplayName(
                    deleteTarget.display_name,
                    deleteTarget.provider
                  )}{" "}
                  ·{" "}
                  <span className="font-mono text-xs">
                    {deleteTarget.model_key}
                  </span>
                </span>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          {deleteError ? (
            <p className="text-sm text-destructive" role="alert">
              {deleteError}
            </p>
          ) : null}
          <DialogFooter>
            <DialogClose asChild>
              <Button
                type="button"
                variant="outline"
                disabled={deleteMutation.isPending}
              >
                Cancel
              </Button>
            </DialogClose>
            <Button
              type="button"
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Removing..." : "Remove"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
