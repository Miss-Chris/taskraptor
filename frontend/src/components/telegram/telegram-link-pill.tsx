import { useCallback, useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { endSession } from "@/lib/auth"
import {
  createTelegramJoinCode,
  fetchTelegramStatus,
  type JoinCodeResponse,
  type TelegramStatusResponse,
} from "@/lib/telegram"
import { cn } from "@/lib/utils"
import { IconBrandTelegram } from "@tabler/icons-react"

function telegramUsernameForUrl(botName: string): string {
  return botName.trim().replace(/^@/, "")
}

export function TelegramLinkPill() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<TelegramStatusResponse | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [joinCode, setJoinCode] = useState<JoinCodeResponse | null>(null)
  const [joinLoading, setJoinLoading] = useState(false)
  const [joinError, setJoinError] = useState<string | null>(null)

  const loadStatus = useCallback(async () => {
    setStatusLoading(true)
    setStatusError(null)
    try {
      const data = await fetchTelegramStatus()
      setStatus(data)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not load Telegram status"
      if (msg === "Not authenticated" || msg === "SESSION_EXPIRED") {
        endSession(queryClient)
        navigate("/login", { replace: true })
        return
      }
      setStatusError(msg)
    } finally {
      setStatusLoading(false)
    }
  }, [navigate, queryClient])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  async function handleGenerateCode() {
    setJoinLoading(true)
    setJoinError(null)
    try {
      const data = await createTelegramJoinCode()
      setJoinCode(data)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not create join code"
      if (msg === "Not authenticated" || msg === "SESSION_EXPIRED") {
        endSession(queryClient)
        navigate("/login", { replace: true })
        return
      }
      setJoinError(msg)
    } finally {
      setJoinLoading(false)
    }
  }

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      setJoinCode(null)
      setJoinError(null)
    }
  }

  const connected = status?.connected === true
  const botName = status?.bot_name?.trim() ?? ""
  const tMe = botName ? `https://t.me/${telegramUsernameForUrl(botName)}` : null

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "flex w-full items-center gap-2 rounded-full border border-sidebar-border bg-sidebar-accent/50 px-3 py-2 text-left text-sm transition-colors",
          "hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        )}
      >
        <IconBrandTelegram className="size-4 shrink-0 text-[#229ED9]" aria-hidden />
        <span className="min-w-0 flex-1 truncate font-medium">
          {statusLoading ? (
            <span className="text-muted-foreground">Telegram…</span>
          ) : statusError ? (
            <span className="text-destructive">Telegram (error)</span>
          ) : connected ? (
            "Telegram linked"
          ) : (
            "Link Telegram"
          )}
        </span>
      </button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Telegram</DialogTitle>
            <DialogDescription>
              Chat with TaskRaptor from Telegram after linking your account.
            </DialogDescription>
          </DialogHeader>

          {statusLoading ? (
            <p className="text-muted-foreground text-sm">Loading connection status…</p>
          ) : statusError ? (
            <div className="space-y-2 text-sm">
              <p className="text-destructive">{statusError}</p>
              <Button type="button" variant="outline" size="sm" onClick={() => void loadStatus()}>
                Retry
              </Button>
            </div>
          ) : connected ? (
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>Your account is linked to Telegram. You can message the bot as usual.</p>
              <p>Disconnecting from Telegram is not available yet.</p>
            </div>
          ) : (
            <div className="space-y-4 text-sm">
              <p className="text-muted-foreground">
                Generate a one-time join code. In Telegram, message the bot with{" "}
                <span className="font-mono text-foreground">JOIN</span> followed by a space and your
                six-character code (example:{" "}
                <span className="font-mono text-foreground">JOIN ABC123</span>). Codes expire after 15
                minutes.
              </p>
              {tMe && (
                <p>
                  <a
                    href={tMe}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary font-medium underline-offset-4 hover:underline"
                  >
                    Open {botName} in Telegram
                  </a>
                </p>
              )}
              {!joinCode && (
                <div className="space-y-2">
                  {joinError && <p className="text-destructive text-sm">{joinError}</p>}
                  <Button
                    type="button"
                    onClick={() => void handleGenerateCode()}
                    disabled={joinLoading}
                  >
                    {joinLoading ? "Generating…" : "Generate join code"}
                  </Button>
                </div>
              )}
              {joinCode && (
                <div className="space-y-2 rounded-xl border border-border bg-muted/40 p-4">
                  <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                    Your code
                  </p>
                  <p className="font-mono text-xl font-semibold tracking-widest">{joinCode.code}</p>
                  <p className="text-muted-foreground text-xs">
                    Expires: {new Date(joinCode.expires_at).toLocaleString()}
                  </p>
                  <p className="pt-1 text-foreground">
                    In Telegram, send:{" "}
                    <kbd className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-sm">
                      JOIN {joinCode.code}
                    </kbd>
                  </p>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
