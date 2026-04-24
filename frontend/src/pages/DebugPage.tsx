import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { clearToken } from "@/lib/auth"
import {
  fetchDebugConversation,
  fetchDebugConversations,
  type DebugAgentRun,
  type DebugConversationBundle,
  type DebugConversationListItem,
  type DebugMessageLog,
} from "@/lib/debug"
import { cn } from "@/lib/utils"
import { IconAlertTriangle, IconBug, IconCheck, IconCopy, IconDatabase, IconRefresh } from "@tabler/icons-react"

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "-"
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function conversationLabel(c: DebugConversationListItem): string {
  const title = c.title || "Untitled conversation"
  return `${title} · ${c.channel.type}`
}

function statusClass(status: string | null | undefined): string {
  if (status === "completed") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
  if (status === "failed") return "border-destructive/30 bg-destructive/10 text-destructive"
  if (status === "running") return "border-sky-500/30 bg-sky-500/10 text-sky-700"
  return "border-border bg-muted text-muted-foreground"
}

function StatusPill({ status }: { status: string | null | undefined }) {
  return (
    <span className={cn("inline-flex rounded-md border px-2 py-0.5 text-xs font-medium", statusClass(status))}>
      {status ?? "no runs"}
    </span>
  )
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="bg-muted max-h-80 overflow-auto rounded-md border p-3 text-xs leading-relaxed">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function logRowClass(actor: string): string {
  if (actor === "user") {
    return "border-sky-500/20 border-l-4 border-l-sky-500/70 bg-sky-500/10"
  }
  if (actor === "assistant") {
    return "border-violet-500/20 border-l-4 border-l-violet-500/70 bg-violet-500/10"
  }
  return "border-l-4 border-l-transparent bg-muted/20"
}

function CopyIdButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => {
        setCopied(false)
      }, 1500)
    } catch {
      /* clipboard unavailable */
    }
  }
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="text-muted-foreground hover:text-foreground size-7 shrink-0"
      onClick={handleCopy}
      title={label}
      aria-label={label}
    >
      {copied ? <IconCheck className="text-emerald-600 size-3.5" /> : <IconCopy className="size-3.5" />}
    </Button>
  )
}

function RunTimeline({ runs }: { runs: DebugAgentRun[] }) {
  if (runs.length === 0) {
    return <p className="text-muted-foreground text-sm">No agent runs recorded.</p>
  }
  return (
    <div className="space-y-2">
      {runs.map((run) => (
        <div key={run.id} className="rounded-md border p-3">
          <div className="flex flex-wrap items-center gap-1">
            <StatusPill status={run.status} />
            <span className="min-w-0 break-all font-mono text-xs">{run.id}</span>
            <CopyIdButton value={run.id} label="Copy agent run ID" />
          </div>
          <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-muted-foreground">Model</dt>
              <dd className="font-medium">{run.model_key}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Created</dt>
              <dd>{formatDate(run.created_at)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Input tokens</dt>
              <dd>{run.input_tokens ?? 0}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Output tokens</dt>
              <dd>{run.output_tokens ?? 0}</dd>
            </div>
          </dl>
          {run.error ? (
            <p className="text-destructive mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs">
              {run.error}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  )
}

function MessageLogTable({ logs }: { logs: DebugMessageLog[] }) {
  if (logs.length === 0) {
    return <p className="text-muted-foreground text-sm">No low-level messages recorded.</p>
  }
  return (
    <div className="overflow-auto rounded-md border">
      <table className="w-full min-w-[640px] text-left text-xs">
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Time</th>
            <th className="px-3 py-2 font-medium">Actor</th>
            <th className="px-3 py-2 font-medium">Tool</th>
            <th className="min-w-0 px-3 py-2 font-medium">Content</th>
            <th className="w-32 whitespace-nowrap px-3 py-2 font-medium">Metadata</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => {
            const hasMetadata = log.metadata && Object.keys(log.metadata).length > 0
            return (
              <tr key={log.id} className={cn("border-border border-t align-top", logRowClass(log.actor))}>
                <td className="text-muted-foreground whitespace-nowrap px-3 py-2">
                  {formatDate(log.created_at)}
                </td>
                <td className="px-3 py-2">
                  <span className="rounded-md border border-border/80 bg-background/50 px-1.5 py-0.5">
                    {log.actor}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <div className="font-medium">{log.tool_name || "—"}</div>
                  {log.tool_call_id ? (
                    <div className="text-muted-foreground font-mono text-[0.65rem]">{log.tool_call_id}</div>
                  ) : null}
                </td>
                <td className="min-w-0 max-w-[min(100%,48rem)] px-3 py-2">
                  <p className="max-h-48 overflow-auto whitespace-pre-wrap break-words">{log.content}</p>
                </td>
                <td className="px-3 py-2 align-top">
                  {hasMetadata ? (
                    <details className="text-left">
                      <summary className="text-muted-foreground cursor-pointer list-none text-[0.65rem] underline decoration-dotted underline-offset-2 [&::-webkit-details-marker]:hidden">
                        View
                      </summary>
                      <pre className="bg-muted/80 mt-2 max-h-40 max-w-xs overflow-auto rounded border p-2 text-[0.65rem] leading-relaxed">
                        {JSON.stringify(log.metadata, null, 2)}
                      </pre>
                    </details>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function DetailView({ bundle }: { bundle: DebugConversationBundle }) {
  const rawSummary = useMemo(
    () => ({
      user: bundle.user,
      channel: bundle.channel,
      conversation: bundle.conversation,
      llm_models: bundle.llm_models,
      automations: bundle.automations,
    }),
    [bundle],
  )

  return (
    <div className="space-y-4">
      <Card size="sm">
        <CardHeader>
          <CardTitle>{bundle.conversation.title || "Untitled conversation"}</CardTitle>
          <CardDescription>
            {bundle.channel.type} · {bundle.channel.name} · updated {formatDate(bundle.conversation.updated_at)}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Conversation</dt>
              <dd className="mt-0.5 flex items-start gap-0.5">
                <span className="min-w-0 break-all font-mono">{bundle.conversation.id}</span>
                <CopyIdButton value={bundle.conversation.id} label="Copy conversation ID" />
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">User</dt>
              <dd className="mt-0.5">{bundle.user.email}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader>
          <CardTitle>Message log</CardTitle>
          <CardDescription>Persisted LLM turns, tool calls, and tool results.</CardDescription>
        </CardHeader>
        <CardContent>
          <MessageLogTable logs={bundle.message_logs} />
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader>
          <CardTitle>Runs</CardTitle>
          <CardDescription>Agent status, model, token totals, and errors.</CardDescription>
        </CardHeader>
        <CardContent>
          <RunTimeline runs={bundle.agent_runs} />
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card size="sm">
          <CardHeader>
            <CardTitle>Related Tasks</CardTitle>
            <CardDescription>Tasks discovered from tool arguments and results.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {bundle.related_tasks.length > 0 ? (
              bundle.related_tasks.map((task) => (
                <div key={task.id} className="rounded-md border p-3 text-sm">
                  <div className="font-medium">{task.name}</div>
                  <div className="text-muted-foreground mt-1 text-xs">
                    {task.status} · priority {task.priority} · {task.id}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-muted-foreground text-sm">No related tasks found.</p>
            )}
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardTitle>Task Changes</CardTitle>
            <CardDescription>Audit rows for related tasks.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {bundle.task_audit_logs.length > 0 ? (
              bundle.task_audit_logs.map((audit) => (
                <div key={audit.id} className="rounded-md border p-3 text-xs">
                  <div className="font-medium">{audit.action}</div>
                  <div className="text-muted-foreground mt-1">
                    {audit.task_name} · {formatDate(audit.created_at)}
                  </div>
                  <details className="mt-2">
                    <summary className="text-muted-foreground cursor-pointer text-[0.7rem]">Old / new values</summary>
                    <pre className="bg-muted/80 mt-2 max-h-40 overflow-auto rounded border p-2 text-[0.65rem] leading-relaxed">
                      {JSON.stringify({ old: audit.old_value, new: audit.new_value }, null, 2)}
                    </pre>
                  </details>
                </div>
              ))
            ) : (
              <p className="text-muted-foreground text-sm">No task audit logs found.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <details className="group rounded-md border">
        <summary className="hover:bg-muted/50 cursor-pointer list-none px-4 py-3 text-sm font-medium [&::-webkit-details-marker]:hidden">
          <span className="text-muted-foreground group-open:text-foreground">Raw snapshot (advanced)</span>
        </summary>
        <div className="border-t p-4 pt-0">
          <p className="text-muted-foreground mb-3 text-xs">
            Redacted config, automations, and full conversation metadata (timezone, prompt length, and channel
            details).
          </p>
          <JsonBlock value={rawSummary} />
        </div>
      </details>
    </div>
  )
}

export function DebugPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get("conversation")
  const [conversations, setConversations] = useState<DebugConversationListItem[]>([])
  const [bundle, setBundle] = useState<DebugConversationBundle | null>(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleError = useCallback(
    (e: unknown) => {
      const msg = e instanceof Error ? e.message : "Failed to load debug data"
      if (msg === "SESSION_EXPIRED") {
        clearToken()
        navigate("/login", { replace: true })
        return
      }
      setError(msg === "NOT_FOUND" ? "Conversation not found." : msg)
    },
    [navigate],
  )

  const loadList = useCallback(async () => {
    setLoadingList(true)
    setError(null)
    try {
      const conversationsData = await fetchDebugConversations()
      setConversations(conversationsData.conversations)
      if (!selectedId && conversationsData.conversations.length > 0) {
        setSearchParams({ conversation: conversationsData.conversations[0].id }, { replace: true })
      }
    } catch (e) {
      handleError(e)
    } finally {
      setLoadingList(false)
    }
  }, [handleError, selectedId, setSearchParams])

  const loadDetail = useCallback(async () => {
    if (!selectedId) {
      setBundle(null)
      return
    }
    setLoadingDetail(true)
    setError(null)
    try {
      setBundle(await fetchDebugConversation(selectedId))
    } catch (e) {
      setBundle(null)
      handleError(e)
    } finally {
      setLoadingDetail(false)
    }
  }, [handleError, selectedId])

  useEffect(() => {
    void loadList()
  }, [loadList])

  useEffect(() => {
    void loadDetail()
  }, [loadDetail])

  function selectConversation(id: string) {
    setSearchParams({ conversation: id }, { replace: true })
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <IconBug className="size-5 shrink-0" />
            Agent Debug
          </h1>
          <p className="text-muted-foreground text-sm">Conversation-scoped agent state for the signed-in user.</p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-2 sm:min-w-[14rem] sm:max-w-md sm:flex-initial">
            <label htmlFor="debug-conversation" className="text-muted-foreground sr-only sm:not-sr-only sm:shrink-0 sm:text-sm">
              Conversation
            </label>
            {loadingList ? (
              <p className="text-muted-foreground text-sm">Loading…</p>
            ) : conversations.length > 0 ? (
              <select
                id="debug-conversation"
                className="border-input bg-background h-9 min-w-0 flex-1 rounded-md border px-3 text-sm shadow-sm sm:min-w-[12rem]"
                value={selectedId ?? ""}
                onChange={(e) => selectConversation(e.target.value)}
              >
                {conversations.map((c) => (
                  <option key={c.id} value={c.id}>
                    {conversationLabel(c)}
                  </option>
                ))}
              </select>
            ) : null}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={loadList}>
            <IconRefresh />
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <div className="text-destructive flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
          <IconAlertTriangle className="mt-0.5 size-4" />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="min-w-0">
        {loadingList ? (
          <Card>
            <CardContent className="text-muted-foreground py-10 text-center text-sm">Loading debug index…</CardContent>
          </Card>
        ) : conversations.length === 0 ? (
          <div className="text-muted-foreground rounded-md border p-6 text-sm">
            <IconDatabase className="mb-2 size-5" />
            No conversations have been recorded yet.
          </div>
        ) : loadingDetail ? (
          <Card>
            <CardContent className="text-muted-foreground py-10 text-center text-sm">Loading conversation snapshot…</CardContent>
          </Card>
        ) : bundle ? (
          <DetailView bundle={bundle} />
        ) : (
          <Card>
            <CardContent className="text-muted-foreground py-10 text-center text-sm">
              Select a conversation to inspect its agent state.
            </CardContent>
          </Card>
        )}
      </div>

      <p className="text-muted-foreground border-t pt-4 text-xs">
        API keys and session tokens are redacted. Message and tool contents are shown for debugging.
      </p>
    </div>
  )
}
