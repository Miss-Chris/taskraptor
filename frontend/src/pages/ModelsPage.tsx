import { useEffect, useMemo, useState } from "react"
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
import { clearToken } from "@/lib/auth"
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

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "No reset date"
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return "No reset date"
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function providerLabel(provider: string): string {
  if (provider === "system_free") return "System"
  return provider.charAt(0).toUpperCase() + provider.slice(1)
}

function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

function ModelSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((index) => (
        <div key={index} className="rounded-lg border border-border p-4">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="mt-3 h-4 w-full max-w-lg" />
          <Skeleton className="mt-4 h-8 w-56" />
        </div>
      ))}
    </div>
  )
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1 text-lg font-semibold tracking-tight">{value}</p>
    </div>
  )
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
        tone === "success" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-700",
        tone === "danger" && "border-destructive/30 bg-destructive/10 text-destructive",
        tone === "neutral" && "border-border bg-muted text-muted-foreground",
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
  onSubmit: (data: UsageModelCreateInput | UsageModelUpdateInput) => Promise<void>
  isSubmitting: boolean
}) {
  const firstOption = supportedModels[0]?.model_key ?? ""
  const isEdit = state.mode === "edit"
  const [modelKey, setModelKey] = useState(isEdit ? state.model.model_key : firstOption)
  const [apiKey, setApiKey] = useState("")
  const [contextLimit, setContextLimit] = useState(
    isEdit ? String(state.model.context_message_limit) : String(DEFAULT_CONTEXT_LIMIT),
  )
  const [activate, setActivate] = useState(isEdit ? state.model.is_active : true)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    const parsedContextLimit = Number(contextLimit)
    if (!Number.isInteger(parsedContextLimit) || parsedContextLimit < 1 || parsedContextLimit > 1024) {
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
      setError(getErrorMessage(err, isEdit ? "Failed to update model" : "Failed to create model"))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit} className="contents">
          <DialogHeader>
            <DialogTitle>{isEdit ? "Edit model" : "Add model"}</DialogTitle>
            <DialogDescription>
              {isEdit ? "Update the API key or context limit for this model." : "Add a user-provided model key."}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="model-key">Model</Label>
              {isEdit ? (
                <Input id="model-key" value={state.model.display_name} disabled />
              ) : (
                <select
                  id="model-key"
                  value={modelKey}
                  onChange={(event) => setModelKey(event.target.value)}
                  className="border-input bg-input/50 h-9 w-full rounded-3xl border px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
                  disabled={supportedModels.length === 0}
                >
                  {supportedModels.map((option) => (
                    <option key={option.model_key} value={option.model_key}>
                      {option.display_name}
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
                placeholder={isEdit ? "Leave blank to keep the current key" : "Provider API key"}
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
                  <p className="text-muted-foreground mt-1 text-xs">This will become the model used by chats.</p>
                </div>
                <Switch id="activate-model" checked={activate} onCheckedChange={setActivate} />
              </div>
            ) : null}

            {error ? (
              <p className="text-destructive text-sm" role="alert">
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
            <Button type="submit" disabled={isSubmitting || (!isEdit && supportedModels.length === 0)}>
              {isSubmitting ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ModelRow({
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
  const canActivate = !model.is_active
  const canEdit = !model.is_system
  const canDelete = !model.is_system && !model.is_active

  return (
    <div className="grid gap-4 p-4 md:grid-cols-[1fr_auto] md:items-start">
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <div className="bg-muted flex size-9 items-center justify-center rounded-lg">
            {model.is_system ? <IconCpu className="text-muted-foreground size-4" /> : <IconKey className="text-muted-foreground size-4" />}
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold">{model.display_name}</h2>
            <p className="text-muted-foreground truncate font-mono text-xs">{model.model_key}</p>
          </div>
          {model.is_active ? <StatusPill tone="success">Active</StatusPill> : null}
          {!model.is_available ? <StatusPill tone="danger">Unavailable</StatusPill> : null}
        </div>

        <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-muted-foreground">Provider</dt>
            <dd className="mt-1 font-medium">{providerLabel(model.provider)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">API key</dt>
            <dd className="mt-1 font-medium">{model.is_system ? "Server-managed" : model.has_api_key ? "Saved" : "Missing"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Context limit</dt>
            <dd className="mt-1 font-medium">{model.context_message_limit} messages</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Updated</dt>
            <dd className="mt-1 font-medium">{formatUsageDate(model.updated_at)}</dd>
          </div>
        </dl>

        {model.is_system ? (
          <div className="mt-4 max-w-xl">
            <UsageMeter
              quota={model.quota}
              quotaUsed={model.quota_used}
              quotaRemaining={model.quota_remaining}
              isAvailable={model.is_available}
            />
            <p className="text-muted-foreground mt-2 text-xs">
              {model.quota_expires_at ? `Resets or expires ${formatDateTime(model.quota_expires_at)}.` : "No reset date is set."}
            </p>
          </div>
        ) : null}

        {model.is_active && !model.is_system ? (
          <p className="text-muted-foreground mt-3 text-xs">Activate another model before deleting this one.</p>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2 md:justify-end">
        {canActivate ? (
          <Button type="button" variant="outline" size="sm" onClick={() => onActivate(model)} disabled={isMutating}>
            <IconCheck />
            Activate
          </Button>
        ) : null}
        {canEdit ? (
          <Button type="button" variant="outline" size="sm" onClick={() => onEdit(model)} disabled={isMutating}>
            <IconSettings />
            Edit
          </Button>
        ) : null}
        {!model.is_system ? (
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => onDelete(model)}
            disabled={!canDelete || isMutating}
            title={!canDelete ? "Activate another model before deleting this one." : undefined}
          >
            <IconTrash />
            Delete
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function ModelsPage() {
  const navigate = useNavigate()
  const usageQuery = useUsageSummaryQuery()
  const createMutation = useCreateLlmModelMutation()
  const updateMutation = useUpdateLlmModelMutation()
  const activateMutation = useActivateLlmModelMutation()
  const deleteMutation = useDeleteLlmModelMutation()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogState, setDialogState] = useState<ModelDialogState>({ mode: "create", model: null })
  const [deleteTarget, setDeleteTarget] = useState<UsageLlmModel | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    const err = usageQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      clearToken()
      navigate("/login", { replace: true })
    }
  }, [navigate, usageQuery.error])

  const summary = usageQuery.data
  const models = useMemo(() => summary?.models ?? [], [summary?.models])
  const activeModel = useMemo(() => models.find((model) => model.is_active) ?? null, [models])
  const activeSystemModel = activeModel?.is_system ? activeModel : null
  const isMutating =
    createMutation.isPending || updateMutation.isPending || activateMutation.isPending || deleteMutation.isPending

  function handleNewModel() {
    setDialogState({ mode: "create", model: null })
    setDialogOpen(true)
  }

  function handleEditModel(model: UsageLlmModel) {
    setDialogState({ mode: "edit", model })
    setDialogOpen(true)
  }

  async function handleSubmitModel(data: UsageModelCreateInput | UsageModelUpdateInput) {
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
      setDeleteError(getErrorMessage(err, "Failed to delete model"))
    }
  }

  return (
    <div className="flex w-full max-w-none flex-1 flex-col gap-5">
      <header className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Models</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            {usageQuery.isLoading
              ? "Loading model settings..."
              : activeModel
                ? `${activeModel.display_name} is active as ${activeModel.is_system ? "the free system model" : "a user-provided key"}.`
                : "No active model found."}
          </p>
        </div>
        <Button type="button" onClick={handleNewModel} disabled={usageQuery.isLoading}>
          <IconPlus />
          Add model
        </Button>
      </header>

      {usageQuery.isError ? (
        <p className="text-destructive text-sm">Could not load model usage.</p>
      ) : (
        <>
          <section className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,2fr)]">
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2">
                <IconCpu className="text-muted-foreground size-4" />
                <h2 className="text-sm font-semibold">Free system usage</h2>
              </div>
              {usageQuery.isLoading ? (
                <div className="mt-4 space-y-3">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-2 w-full" />
                  <Skeleton className="h-4 w-56" />
                </div>
              ) : activeSystemModel ? (
                <div className="mt-4">
                  <UsageMeter
                    quota={activeSystemModel.quota}
                    quotaUsed={activeSystemModel.quota_used}
                    quotaRemaining={activeSystemModel.quota_remaining}
                    isAvailable={activeSystemModel.is_available}
                  />
                  <p className="text-muted-foreground mt-2 text-xs">
                    {activeSystemModel.quota_expires_at
                      ? `Resets or expires ${formatDateTime(activeSystemModel.quota_expires_at)}.`
                      : "No reset date is set."}
                  </p>
                </div>
              ) : (
                <p className="text-muted-foreground mt-4 text-sm">A user-provided model is active.</p>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <StatTile label="Total tokens" value={formatTokenCount(summary?.totals.total_tokens)} />
              <StatTile label="Input tokens" value={formatTokenCount(summary?.totals.input_tokens)} />
              <StatTile label="Output tokens" value={formatTokenCount(summary?.totals.output_tokens)} />
              <StatTile label="Recent runs" value={formatTokenCount(summary?.totals.recent_run_count)} />
              <StatTile label="Failed runs" value={formatTokenCount(summary?.totals.failed_run_count)} />
            </div>
          </section>

          {summary?.totals.recent_since ? (
            <p className="text-muted-foreground text-xs">Usage totals since {formatDateTime(summary.totals.recent_since)}.</p>
          ) : null}

          {actionError ? (
            <p className="text-destructive text-sm" role="alert">
              {actionError}
            </p>
          ) : null}

          {usageQuery.isLoading ? (
            <ModelSkeleton />
          ) : models.length > 0 ? (
            <div className="divide-y divide-border rounded-lg border border-border">
              {models.map((model) => (
                <ModelRow
                  key={model.id}
                  model={model}
                  onActivate={handleActivateModel}
                  onEdit={handleEditModel}
                  onDelete={handleDeleteClick}
                  isMutating={isMutating}
                />
              ))}
            </div>
          ) : (
            <div className="flex min-h-[18rem] flex-col items-center justify-center gap-4 text-center">
              <div className="bg-muted flex size-12 items-center justify-center rounded-full">
                <IconCpu className="text-muted-foreground size-6" />
              </div>
              <div>
                <p className="text-sm font-medium">No models available</p>
                <p className="text-muted-foreground mt-1 text-sm">Add a model to start using TaskRaptor.</p>
              </div>
              <Button type="button" onClick={handleNewModel}>
                <IconPlus />
                Add model
              </Button>
            </div>
          )}
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
            <DialogTitle>Delete model?</DialogTitle>
            <DialogDescription>
              This removes the saved API key and model settings.
              {deleteTarget ? (
                <span className="mt-2 block font-medium text-foreground">
                  {deleteTarget.display_name} · {deleteTarget.model_key}
                </span>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          {deleteError ? (
            <p className="text-destructive text-sm" role="alert">
              {deleteError}
            </p>
          ) : null}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={deleteMutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <Button type="button" variant="destructive" onClick={handleConfirmDelete} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
