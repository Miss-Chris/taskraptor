/* eslint-disable react-hooks/set-state-in-effect -- local UI state tracks OpenAPI query + polling */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { FormEvent, KeyboardEvent, ReactNode } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { clearToken } from "@/lib/auth"
import {
  fetchChatMessagesAfter,
  fetchChatRun,
  type ChatConversation,
  type ChatMessage,
  type ChatRun,
} from "@/lib/chat"
import { cn } from "@/lib/utils"
import {
  useChatConversationQuery,
  useSendChatMessageMutation,
  useStartChatConversationMutation,
} from "@/queries/chat"
import { IconAlertTriangle, IconMessagePlus, IconSend } from "@tabler/icons-react"

const POLL_MS = 1500
const INLINE_MARKDOWN_PATTERN = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g

function isActiveRun(run: ChatRun | null | undefined): run is ChatRun {
  return run?.status === "pending" || run?.status === "running"
}

function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const seen = new Set(current.map((message) => message.id))
  const next = [...current]
  for (const message of incoming) {
    if (!seen.has(message.id)) {
      seen.add(message.id)
      next.push(message)
    }
  }
  return next
}

function mergeRun(current: ChatRun[], incoming: ChatRun): ChatRun[] {
  const rest = current.filter((run) => run.id !== incoming.id)
  return [incoming, ...rest]
}

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  })
}

function conversationTitle(conversation: ChatConversation | null): string {
  if (!conversation) return "Chat"
  if (conversation.title.trim()) return conversation.title
  return "New chat"
}

function parseInlineMarkdown(text: string): ReactNode[] {
  return text.split(INLINE_MARKDOWN_PATTERN).map((part, index) => {
    if (!part) return null
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={index} className="bg-muted rounded px-1 py-0.5 font-mono text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      )
    }
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    if (linkMatch) {
      const label = linkMatch[1] ?? ""
      const href = linkMatch[2]
      if (!href) return part
      const safeHref = href.startsWith("http://") || href.startsWith("https://") ? href : undefined
      return safeHref ? (
        <a
          key={index}
          href={safeHref}
          target="_blank"
          rel="noreferrer"
          className="text-primary underline underline-offset-2"
        >
          {label}
        </a>
      ) : (
        <span key={index}>{label}</span>
      )
    }
    return part
  })
}

function MarkdownMessage({ content }: { content: string }) {
  const lines = content.split("\n")
  const blocks: ReactNode[] = []
  let paragraph: string[] = []
  let listItems: string[] = []
  let codeLines: string[] = []
  let inCode = false

  const flushParagraph = () => {
    if (paragraph.length === 0) return
    const text = paragraph.join("\n")
    blocks.push(
      <p key={`p-${blocks.length}`} className="whitespace-pre-wrap">
        {parseInlineMarkdown(text)}
      </p>,
    )
    paragraph = []
  }

  const flushList = () => {
    if (listItems.length === 0) return
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="list-disc space-y-1 pl-5">
        {listItems.map((item, index) => (
          <li key={index}>{parseInlineMarkdown(item)}</li>
        ))}
      </ul>,
    )
    listItems = []
  }

  const flushCode = () => {
    blocks.push(
      <pre key={`code-${blocks.length}`} className="bg-muted overflow-x-auto rounded-md border p-3 text-xs">
        <code>{codeLines.join("\n")}</code>
      </pre>,
    )
    codeLines = []
  }

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        flushCode()
        inCode = false
      } else {
        flushParagraph()
        flushList()
        inCode = true
      }
      continue
    }

    if (inCode) {
      codeLines.push(line)
      continue
    }

    if (line.trim() === "") {
      flushParagraph()
      flushList()
      continue
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/)
    if (headingMatch) {
      flushParagraph()
      flushList()
      const marker = headingMatch[1] ?? ""
      const text = headingMatch[2] ?? ""
      const level = marker.length
      const className = level === 1 ? "text-base font-semibold" : "text-sm font-semibold"
      blocks.push(
        <p key={`h-${blocks.length}`} className={className}>
          {parseInlineMarkdown(text)}
        </p>,
      )
      continue
    }

    const quoteMatch = line.match(/^>\s?(.+)$/)
    if (quoteMatch) {
      flushParagraph()
      flushList()
      blocks.push(
        <blockquote
          key={`quote-${blocks.length}`}
          className="border-l-2 border-border pl-3 text-muted-foreground"
        >
          {parseInlineMarkdown(quoteMatch[1] ?? "")}
        </blockquote>,
      )
      continue
    }

    const listMatch = line.match(/^[-*]\s+(.+)$/)
    if (listMatch) {
      flushParagraph()
      listItems.push(listMatch[1] ?? "")
      continue
    }

    flushList()
    paragraph.push(line)
  }

  if (inCode) flushCode()
  flushParagraph()
  flushList()

  return <div className="space-y-3 break-words">{blocks}</div>
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user"
  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <article
        className={cn(
          "max-w-[min(44rem,85%)] rounded-lg border px-4 py-3 text-sm leading-relaxed shadow-sm",
          isUser
            ? "border-border bg-muted text-foreground"
            : "border-border bg-card/70 text-card-foreground",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : (
          <MarkdownMessage content={message.content} />
        )}
        <time
          className={cn(
            "mt-2 block text-[0.7rem]",
            "text-muted-foreground",
          )}
        >
          {formatTime(message.created_at)}
        </time>
      </article>
    </div>
  )
}

export function ChatPage() {
  const navigate = useNavigate()
  const { conversationId } = useParams()
  const [conversation, setConversation] = useState<ChatConversation | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [runs, setRuns] = useState<ChatRun[]>([])
  const [input, setInput] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const conversationQuery = useChatConversationQuery(conversationId)
  const startChat = useStartChatConversationMutation()
  const sendMessage = useSendChatMessageMutation()
  const starting = startChat.isPending
  const sending = sendMessage.isPending
  const loading = Boolean(conversationId) && conversationQuery.isPending

  const latestRun = runs[0] ?? conversation?.latest_run ?? null
  const activeRun = isActiveRun(latestRun) ? latestRun : null
  const canSend = input.trim().length > 0 && !sending && !starting

  const handleAuthError = useCallback(
    (message: string) => {
      if (message === "SESSION_EXPIRED" || message === "Not authenticated") {
        clearToken()
        navigate("/login", { replace: true })
        return true
      }
      return false
    },
    [navigate],
  )

  useEffect(() => {
    if (!conversationId) {
      setConversation(null)
      setMessages([])
      setRuns([])
      setError(null)
      setRunError(null)
      setNotFound(false)
      return
    }

    setError(null)
    setRunError(null)
    setNotFound(false)
  }, [conversationId])

  useEffect(() => {
    if (!conversationId || !conversationQuery.data) return
    setConversation(conversationQuery.data.conversation)
    setMessages(conversationQuery.data.messages)
    setRuns(conversationQuery.data.runs)
    const failedRun = conversationQuery.data.runs.find((run) => run.status === "failed" && run.error)
    setRunError(failedRun?.error ?? null)
  }, [conversationId, conversationQuery.data])

  useEffect(() => {
    if (!conversationId || !conversationQuery.error) return
    const message =
      conversationQuery.error instanceof Error ? conversationQuery.error.message : "Failed to load conversation"
    if (handleAuthError(message)) return
    setConversation(null)
    setMessages([])
    setRuns([])
    if (message === "NOT_FOUND") {
      setNotFound(true)
    } else {
      setError(message)
    }
  }, [conversationId, conversationQuery.error, handleAuthError])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ block: "end" })
  }, [messages.length, activeRun?.id])

  useEffect(() => {
    if (loading) return
    const frame = window.requestAnimationFrame(() => {
      textareaRef.current?.focus()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [conversationId, loading])

  useEffect(() => {
    if (!conversationId || !activeRun) return

    let cancelled = false
    const poll = async () => {
      try {
        const lastMessageId = messages[messages.length - 1]?.id
        const [nextRun, nextMessages] = await Promise.all([
          fetchChatRun(activeRun.id),
          lastMessageId ? fetchChatMessagesAfter(conversationId, lastMessageId) : Promise.resolve(null),
        ])
        if (cancelled) return
        setRuns((current) => mergeRun(current, nextRun))
        if (nextRun.status === "failed" && nextRun.error) {
          setRunError(nextRun.error)
        }
        if (nextMessages?.messages.length) {
          setMessages((current) => mergeMessages(current, nextMessages.messages))
          window.dispatchEvent(new Event("taskraptor:chat-updated"))
        }
        if (nextRun.status === "completed") {
          window.dispatchEvent(new Event("taskraptor:chat-updated"))
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to update chat"
        if (!handleAuthError(message) && message !== "NOT_FOUND") {
          setError(message)
        }
      }
    }

    const interval = window.setInterval(poll, POLL_MS)
    void poll()
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [activeRun, conversationId, handleAuthError, messages])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = input.trim()
    if (!content || sending || starting) return

    setError(null)
    setRunError(null)
    try {
      if (!conversationId) {
        const result = await startChat.mutateAsync({
          body: { content },
        })
        setInput("")
        setConversation(result.conversation)
        setMessages([result.message])
        setRuns([result.run])
        window.dispatchEvent(new Event("taskraptor:chat-updated"))
        navigate(`/c/${result.conversation.id}`)
        return
      }

      const result = await sendMessage.mutateAsync({
        params: { path: { conversation_id: conversationId } },
        body: { content },
      })
      setInput("")
      setMessages((current) => mergeMessages(current, [result.message]))
      setRuns((current) => mergeRun(current, result.run))
      window.dispatchEvent(new Event("taskraptor:chat-updated"))
      textareaRef.current?.focus()
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to send message"
      if (!handleAuthError(message)) setError(message)
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) return
    event.preventDefault()
    event.currentTarget.form?.requestSubmit()
  }

  const headerDescription = useMemo(() => {
    if (!conversation) return "Draft"
    if (activeRun) return "Agent is working"
    if (messages.length === 0) return "No messages yet"
    return `${messages.length} message${messages.length === 1 ? "" : "s"}`
  }, [activeRun, conversation, messages.length])

  if (loading) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center">
        <p className="text-muted-foreground text-sm">Loading chat...</p>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="mx-auto flex h-full min-h-0 w-full max-w-lg flex-col items-center justify-center gap-4 text-center">
        <IconAlertTriangle className="text-muted-foreground size-8" />
        <div className="space-y-2">
          <h1 className="text-xl font-semibold tracking-tight">Conversation not found</h1>
          <p className="text-muted-foreground text-sm">
            This conversation is unavailable or belongs to another account.
          </p>
        </div>
        <Button type="button" onClick={() => navigate("/")}>
          <IconMessagePlus />
          New Chat
        </Button>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 w-full max-w-none flex-1 flex-col">
      <header className="border-border flex shrink-0 items-start justify-between gap-4 border-b pb-4">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight">
            {conversationId ? conversationTitle(conversation) : "TaskRaptor chat"}
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">{headerDescription}</p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => navigate("/")}>
          <IconMessagePlus />
          New Chat
        </Button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain py-4">
        {messages.length === 0 ? (
          <div className="flex flex-1 items-center justify-center py-16 text-center">
            <p className="text-muted-foreground max-w-sm text-sm leading-relaxed">
              Send the first message to start a conversation.
            </p>
          </div>
        ) : (
          messages.map((message) => <MessageBubble key={message.id} message={message} />)
        )}
        {activeRun ? (
          <div className="flex justify-start">
            <div className="border-border bg-muted text-muted-foreground rounded-lg border px-4 py-3 text-sm">
              Thinking...
            </div>
          </div>
        ) : null}
        <div ref={scrollRef} />
      </div>

      <form onSubmit={handleSubmit} className="bg-background shrink-0 border-t pt-4">
        {error ? <p className="text-destructive mb-3 text-sm">{error}</p> : null}
        {runError ? (
          <p className="text-destructive mb-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
            {runError}
          </p>
        ) : null}
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            rows={2}
            placeholder="Message TaskRaptor"
            className="border-input bg-background focus-visible:ring-ring min-h-12 flex-1 resize-none rounded-lg border px-3 py-2 text-sm leading-relaxed outline-none transition-[border-color,box-shadow] placeholder:text-muted-foreground focus-visible:ring-3 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={sending || starting}
          />
          <Button type="submit" size="icon" disabled={!canSend} aria-label="Send message">
            <IconSend />
          </Button>
        </div>
      </form>
    </div>
  )
}
