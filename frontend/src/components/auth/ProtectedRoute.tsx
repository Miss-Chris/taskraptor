import type { ReactNode } from "react"
import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Navigate, useLocation } from "react-router-dom"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { fetchMe, getToken, updateTimezone } from "@/lib/auth"
import { getBrowserTimezone, timezoneOptionsWithSelected } from "@/lib/timezones"

function RequiredTimezoneDialog() {
  const queryClient = useQueryClient()
  const initialTimezone = getBrowserTimezone() ?? "UTC"
  const [timezone, setTimezone] = useState(initialTimezone)
  const [error, setError] = useState<string | null>(null)
  const options = useMemo(
    () => timezoneOptionsWithSelected(timezone),
    [timezone]
  )
  const updateMutation = useMutation({
    mutationFn: updateTimezone,
    async onSuccess() {
      setError(null)
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] })
    },
    onError(err) {
      setError(err instanceof Error ? err.message : "Failed to save timezone.")
    },
  })

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    updateMutation.mutate(timezone)
  }

  return (
    <Dialog open>
      <DialogContent
        showCloseButton={false}
        onEscapeKeyDown={(event) => event.preventDefault()}
        onPointerDownOutside={(event) => event.preventDefault()}
      >
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>What is your home timezone?</DialogTitle>
            <DialogDescription>
              Scheduled automations and date handling will always run in your
              timezone.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-5 grid gap-2">
            <Label htmlFor="required-timezone">Timezone</Label>
            <select
              id="required-timezone"
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
              className="h-9 w-full rounded-3xl border border-input bg-input/50 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50"
              disabled={updateMutation.isPending}
            >
              {options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          {error ? (
            <p className="mt-3 text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter className="mt-5">
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation()
  const token = getToken()
  const meQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: fetchMe,
    enabled: Boolean(token),
    retry: false,
    staleTime: 60_000,
  })

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (meQuery.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <p className="text-sm text-muted-foreground">Checking session...</p>
      </div>
    )
  }

  if (meQuery.isError) {
    return null
  }

  if (meQuery.data.timezone === null) {
    return <RequiredTimezoneDialog />
  }

  return <>{children}</>
}
