import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { AutomationDialog } from "@/components/automations/AutomationDialog"
import {
  AutomationListItem,
  AutomationListSkeleton,
} from "@/components/automations/AutomationListItem"
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
import { useDocumentTitle } from "@/hooks/use-document-title"
import { endSession } from "@/lib/auth"
import type {
  Automation,
  AutomationCreateInput,
  AutomationUpdateInput,
} from "@/lib/automations"
import {
  useAutomationsQuery,
  useCreateAutomationMutation,
  useDeleteAutomationMutation,
  useTestAutomationMutation,
  useUpdateAutomationMutation,
} from "@/queries/automations"
import { IconPlus, IconRobot } from "@tabler/icons-react"

export function AutomationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const automationsQuery = useAutomationsQuery()
  const createMutation = useCreateAutomationMutation()
  const updateMutation = useUpdateAutomationMutation()
  const deleteMutation = useDeleteAutomationMutation()
  const testMutation = useTestAutomationMutation()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingAutomation, setEditingAutomation] = useState<Automation | null>(
    null
  )
  const [deleteTarget, setDeleteTarget] = useState<Automation | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [testingAutomationId, setTestingAutomationId] = useState<string | null>(
    null
  )
  const [testError, setTestError] = useState<string | null>(null)

  useDocumentTitle("Automations")

  useEffect(() => {
    const err = automationsQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      endSession(queryClient)
      navigate("/login", { replace: true })
    }
  }, [automationsQuery.error, navigate, queryClient])

  const automations = automationsQuery.data?.automations ?? []
  const isEditMode = editingAutomation != null

  function handleNewAutomation() {
    setEditingAutomation(null)
    setDialogOpen(true)
  }

  function handleEditAutomation(automation: Automation) {
    setEditingAutomation(automation)
    setDialogOpen(true)
  }

  async function handleSubmit(
    data: AutomationCreateInput | AutomationUpdateInput
  ) {
    if (isEditMode && editingAutomation) {
      await updateMutation.mutateAsync({
        params: { path: { automation_id: editingAutomation.id } },
        body: data as AutomationUpdateInput,
      })
    } else {
      await createMutation.mutateAsync({
        body: data as AutomationCreateInput,
      })
    }
  }

  function handleDeleteClick(automation: Automation) {
    setDeleteTarget(automation)
    setDeleteError(null)
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return
    setDeleteError(null)
    try {
      await deleteMutation.mutateAsync({
        params: { path: { automation_id: deleteTarget.id } },
      })
      setDeleteTarget(null)
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete automation"
      )
    }
  }

  async function handleToggleActive(automation: Automation, isActive: boolean) {
    await updateMutation.mutateAsync({
      params: { path: { automation_id: automation.id } },
      body: { is_active: isActive },
    })
  }

  async function handleTestAutomation(automation: Automation) {
    setTestingAutomationId(automation.id)
    setTestError(null)
    try {
      await testMutation.mutateAsync({
        params: { path: { automation_id: automation.id } },
      })
    } catch (err) {
      setTestError(
        err instanceof Error ? err.message : "Failed to test automation"
      )
    } finally {
      setTestingAutomationId(null)
    }
  }

  return (
    <div className="flex w-full max-w-none flex-1 flex-col gap-5">
      <header className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Automations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {automationsQuery.data?.count ?? automations.length} scheduled
            automations
          </p>
        </div>
        <Button type="button" onClick={handleNewAutomation}>
          <IconPlus />
          New Automation
        </Button>
      </header>

      {automationsQuery.isLoading ? (
        <AutomationListSkeleton count={3} />
      ) : automationsQuery.isError ? (
        <p className="text-sm text-destructive">Could not load automations</p>
      ) : automations.length > 0 ? (
        <>
          {testError ? (
            <p className="text-sm text-destructive" role="alert">
              {testError}
            </p>
          ) : null}
          <div className="divide-y divide-border rounded-lg border border-border">
            {automations.map((automation) => (
              <AutomationListItem
                key={automation.id}
                automation={automation}
                onTest={handleTestAutomation}
                onEdit={handleEditAutomation}
                onDelete={handleDeleteClick}
                onToggleActive={handleToggleActive}
                isTesting={testingAutomationId === automation.id}
                isUpdating={updateMutation.isPending}
                isDeleting={deleteMutation.isPending}
              />
            ))}
          </div>
        </>
      ) : (
        <div className="flex min-h-[18rem] flex-col items-center justify-center gap-4 text-center">
          <div className="flex size-12 items-center justify-center rounded-full bg-muted">
            <IconRobot className="size-6 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium">No automations yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Create an automation to run prompts on a schedule
            </p>
          </div>
          <Button type="button" onClick={handleNewAutomation}>
            <IconPlus />
            Create your first automation
          </Button>
        </div>
      )}

      <AutomationDialog
        automation={editingAutomation}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmit={handleSubmit}
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
            <DialogTitle>Delete automation?</DialogTitle>
            <DialogDescription>
              This will permanently remove the scheduled automation.
              {deleteTarget && (
                <span className="mt-2 block font-medium text-foreground">
                  "{deleteTarget.prompt.slice(0, 60)}
                  {deleteTarget.prompt.length > 60 ? "..." : ""}"
                </span>
              )}
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
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
