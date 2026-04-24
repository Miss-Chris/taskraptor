import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { clearToken } from "@/lib/auth"
import {
  fetchDebugConversation,
  fetchDebugConversations,
  fetchDebugSummary,
  type DebugAgentRun,
  type DebugConversationBundle,
  type DebugConversationListItem,
  type DebugMessageLog,
  type DebugSummary,
} from "@/lib/debug"
import { cn } from "@/lib/utils"
import { IconAlertTriangle, IconBug, IconDatabase, IconRefresh } from "@tabler/icons-react"

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "-"
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
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

function ConversationButton({
  conversation,
  active,
  onClick,
}: {
  conversation: DebugConversationListItem
  active: boolean
  onClick: () => void
}) {
  const title = conversation.title || "Untitled conversation"
  return (
    <button
      type="button"
      className={cn(
        "hover:bg-muted w-full rounded-md border p-3 text-left transition",
        active ? "border-primary bg-primary/5" : "border-border bg-background",
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{title}</p>
          <p className="text-muted-foreground mt-1 truncate text-xs">
            {conversation.channel.type} · {conversation.visible_message_count} visible ·{" "}
            {conversation.message_log_count} logs
          </p>
        </div>
        <StatusPill status={conversation.latest_run_status} />
      </div>
      {conversation.latest_visible_message ? (
        <p className="text-muted-foreground mt-2 line-clamp-2 text-xs">
          {conversation.latest_visible_role}: {conversation.latest_visible_message}
        </p>
      ) : null}
      <p className="text-muted-foreground mt-2 text-xs">{formatDate(conversation.updated_at)}</p>
    </button>
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
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={run.status} />
            <span className="font-mono text-xs">{run.id}</span>
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
      <table className="w-full min-w-[760px] text-left text-xs">
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Time</th>
            <th className="px-3 py-2 font-medium">Actor</th>
            <th className="px-3 py-2 font-medium">Tool</th>
            <th className="px-3 py-2 font-medium">Content</th>
            <th className="px-3 py-2 font-medium">Metadata</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} className="border-t align-top">
              <td className="text-muted-foreground whitespace-nowrap px-3 py-2">
                {formatDate(log.created_at)}
              </td>
              <td className="px-3 py-2">
                <span className="rounded-md border px-1.5 py-0.5">{log.actor}</span>
              </td>
              <td className="px-3 py-2">
                <div className="font-medium">{log.tool_name || "-"}</div>
                <div className="text-muted-foreground font-mono">{log.tool_call_id || ""}</div>
              </td>
              <td className="max-w-sm px-3 py-2">
                <p className="max-h-24 overflow-auto whitespace-pre-wrap">{log.content}</p>
              </td>
              <td className="max-w-xs px-3 py-2">
                <pre className="max-h-24 overflow-auto whitespace-pre-wrap">
                  {JSON.stringify(log.metadata)}
                </pre>
              </td>
            </tr>
          ))}
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
            {bundle.channel.type} · {bundle.channel.name} · updated{" "}
            {formatDate(bundle.conversation.updated_at)}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-muted-foreground">Conversation</dt>
              <dd className="font-mono">{bundle.conversation.id}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">User</dt>
              <dd>{bundle.user.email}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Timezone</dt>
              <dd>{bundle.user.timezone}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Prompt instructions</dt>
              <dd>{bundle.user.prompt_instructions_length} chars</dd>
            </div>
          </dl>
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

      <Card size="sm">
        <CardHeader>
          <CardTitle>Visible Chat</CardTitle>
          <CardDescription>Messages shown to the user in the web channel.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {bundle.visible_messages.length > 0 ? (
            bundle.visible_messages.map((msg) => (
              <div key={msg.id} className="rounded-md border p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-md border px-1.5 py-0.5 font-medium">{msg.role}</span>
                  <span className="text-muted-foreground">{formatDate(msg.created_at)}</span>
                  {msg.agent_run_id ? (
                    <span className="text-muted-foreground font-mono">run {msg.agent_run_id}</span>
                  ) : null}
                </div>
                <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
              </div>
            ))
          ) : (
            <p className="text-muted-foreground text-sm">No visible web messages.</p>
          )}
        </CardContent>
      </Card>

      <Card size="sm">
        <CardHeader>
          <CardTitle>Low-Level Log</CardTitle>
          <CardDescription>Persisted LLM turns, tool calls, and tool results.</CardDescription>
        </CardHeader>
        <CardContent>
          <MessageLogTable logs={bundle.message_logs} />
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
                  <pre className="mt-2 overflow-auto whitespace-pre-wrap">
                    {JSON.stringify({ old: audit.old_value, new: audit.new_value }, null, 2)}
                  </pre>
                </div>
              ))
            ) : (
              <p className="text-muted-foreground text-sm">No task audit logs found.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card size="sm">
        <CardHeader>
          <CardTitle>Raw Snapshot</CardTitle>
          <CardDescription>Redacted config, automations, and conversation metadata.</CardDescription>
        </CardHeader>
        <CardContent>
          <JsonBlock value={rawSummary} />
        </CardContent>
      </Card>
    </div>
  )
}

export function DebugPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get("conversation")
  const [summary, setSummary] = useState<DebugSummary | null>(null)
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
      const [summaryData, conversationsData] = await Promise.all([
        fetchDebugSummary(),
        fetchDebugConversations(),
      ])
      setSummary(summaryData)
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Agent Debug</h1>
          <p className="text-muted-foreground text-sm">
            Conversation-scoped agent state for the signed-in user.
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={loadList}>
          <IconRefresh />
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="text-destructive flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
          <IconAlertTriangle className="mt-0.5 size-4" />
          <span>{error}</span>
        </div>
      ) : null}

      {summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(summary.counts).map(([key, value]) => (
            <div key={key} className="rounded-md border p-3">
              <div className="text-muted-foreground text-xs capitalize">{key.replace(/_/g, " ")}</div>
              <div className="mt-1 text-lg font-semibold">{value}</div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Card size="sm" className="lg:sticky lg:top-4 lg:max-h-[calc(100vh-7rem)]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <IconBug className="size-4" />
              Conversations
            </CardTitle>
            <CardDescription>{conversations.length} conversation snapshots</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 overflow-auto">
            {loadingList ? (
              <p className="text-muted-foreground text-sm">Loading debug index...</p>
            ) : conversations.length > 0 ? (
              conversations.map((conversation) => (
                <ConversationButton
                  key={conversation.id}
                  conversation={conversation}
                  active={conversation.id === selectedId}
                  onClick={() => selectConversation(conversation.id)}
                />
              ))
            ) : (
              <div className="text-muted-foreground rounded-md border p-4 text-sm">
                <IconDatabase className="mb-2 size-4" />
                No conversations have been recorded yet.
              </div>
            )}
          </CardContent>
        </Card>

        <div className="min-w-0">
          {loadingDetail ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                Loading conversation snapshot...
              </CardContent>
            </Card>
          ) : bundle ? (
            <DetailView bundle={bundle} />
          ) : (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                Select a conversation to inspect its agent state.
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <Separator />
      <p className="text-muted-foreground text-xs">
        API keys and session tokens are redacted. Message and tool contents are shown for debugging.
      </p>
    </div>
  )
}
