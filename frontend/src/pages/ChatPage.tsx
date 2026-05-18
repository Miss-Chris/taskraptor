import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { FormEvent, KeyboardEvent, ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { endSession } from "@/lib/auth"
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
import {
  IconAlertTriangle,
  IconMessagePlus,
  IconSend,
} from "@tabler/icons-react"

const POLL_MS = 1500
const INLINE_MARKDOWN_PATTERN = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g
const GROUP_GAP_MS = 5 * 60 * 1000

const EXAMPLE_PROMPTS = [
  "What tasks do I have due today?",
  "Add a task: review project proposal by Friday",
  "What's on my schedule this week?",
  "Show me tasks I haven't started yet",
]

function isActiveRun(run: ChatRun | null | undefined): run is ChatRun {
  return run?.status === "pending" || run?.status === "running"
}

function mergeMessages(
  current: ChatMessage[],
  incoming: ChatMessage[]
): ChatMessage[] {
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

function groupMessages(
  messages: ChatMessage[]
): Array<{ message: ChatMessage; isGroupStart: boolean }> {
  return messages.map((message, index) => {
    const prev = messages[index - 1]
    const isGroupStart =
      !prev ||
      prev.role !== message.role ||
      new Date(message.created_at).getTime() -
        new Date(prev.created_at).getTime() >
        GROUP_GAP_MS
    return { message, isGroupStart }
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
        <code
          key={index}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    if (linkMatch) {
      const label = linkMatch[1] ?? ""
      const href = linkMatch[2]
      if (!href) return part
      const safeHref =
        href.startsWith("http://") || href.startsWith("https://")
          ? href
          : undefined
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
      </p>
    )
    paragraph = []
  }

  const flushList = () => {
    if (listItems.length === 0) return
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="list-disc space-y-0.5 pl-4">
        {listItems.map((item, index) => (
          <li key={index}>{parseInlineMarkdown(item)}</li>
        ))}
      </ul>
    )
    listItems = []
  }

  const flushCode = () => {
    blocks.push(
      <pre
        key={`code-${blocks.length}`}
        className="overflow-x-auto rounded-md border bg-muted p-3 text-xs"
      >
        <code>{codeLines.join("\n")}</code>
      </pre>
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
      const HeadingTag = (
        level === 1 ? "h2" : level === 2 ? "h3" : "h4"
      ) as "h2" | "h3" | "h4"
      const className =
        level === 1
          ? "text-sm font-semibold text-foreground"
          : "text-sm font-medium text-muted-foreground"
      blocks.push(
        <HeadingTag key={`h-${blocks.length}`} className={className}>
          {parseInlineMarkdown(text)}
        </HeadingTag>
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
        </blockquote>
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

  return <div className="space-y-2 break-words">{blocks}</div>
}

function MessageBubble({
  message,
  isGroupStart,
}: {
  message: ChatMessage
  isGroupStart: boolean
}) {
  const isUser = message.role === "user"
  return (
    <div
      className={cn(
        "group flex w-full",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <article
        className={cn(
          "max-w-[min(44rem,85%)] rounded-xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground"
            : "border border-border bg-card/70 text-card-foreground shadow-sm"
        )}
      >
        {isUser ? (
          <p className="break-words whitespace-pre-wrap">{message.content}</p>
        ) : (
          <MarkdownMessage content={message.content} />
        )}
        <time
          dateTime={message.created_at}
          className={cn(
            "mt-1 block text-[0.68rem] transition-opacity duration-150",
            isUser ? "text-primary-foreground/50" : "text-muted-foreground/70",
            isGroupStart
              ? "opacity-100"
              : "opacity-0 group-hover:opacity-100"
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
  const queryClient = useQueryClient()
  const { conversationId } = useParams()
  const [conversation, setConversation] = useState<ChatConversation | null>(
    null
  )
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [runs, setRuns] = useState<ChatRun[]>([])
  const [input, setInput] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const messagesRef = useRef<ChatMessage[]>([])
  const conversationQuery = useChatConversationQuery(conversationId)
  const startChat = useStartChatConversationMutation()
  const sendMessage = useSendChatMessageMutation()
  const starting = startChat.isPending
  const sending = sendMessage.isPending
  const loading = Boolean(conversationId) && conversationQuery.isPending

  const latestRun = runs[0] ?? conversation?.latest_run ?? null
  const activeRun = isActiveRun(latestRun) ? latestRun : null
  const activeRunId = activeRun?.id ?? null
  const canSend = input.trim().length > 0 && !sending && !starting

  const focusComposer = useCallback(() => {
    window.requestAnimationFrame(() => {
      textareaRef.current?.focus()
    })
  }, [])

  useDocumentTitle(
    loading
      ? "Loading chat"
      : notFound
        ? "Conversation not found"
        : conversationId
          ? conversationTitle(conversation)
          : "TaskRaptor chat"
  )

  const handleAuthError = useCallback(
    (message: string) => {
      if (message === "SESSION_EXPIRED" || message === "Not authenticated") {
        endSession(queryClient)
        navigate("/login", { replace: true })
        return true
      }
      return false
    },
    [navigate, queryClient]
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
    const failedRun = conversationQuery.data.runs.find(
      (run) => run.status === "failed" && run.error
    )
    setRunError(failedRun?.error ? friendlyRunError(failedRun.error) : null)
  }, [conversationId, conversationQuery.data])

  useEffect(() => {
    if (!conversationId || !conversationQuery.error) return
    const message =
      conversationQuery.error instanceof Error
        ? conversationQuery.error.message
        : "Failed to load conversation"
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
    messagesRef.current = messages
  }, [messages])

  useEffect(() => {
    if (loading) return
    const frame = window.requestAnimationFrame(() => {
      textareaRef.current?.focus()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [conversationId, loading])

  useEffect(() => {
    if (!conversationId || !activeRunId) return

    let cancelled = false
    let inFlight = false
    const poll = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const lastMessageId = messagesRef.current.at(-1)?.id
        const [nextRun, nextMessages] = await Promise.all([
          fetchChatRun(activeRunId),
          lastMessageId
            ? fetchChatMessagesAfter(conversationId, lastMessageId)
            : Promise.resolve(null),
        ])
        if (cancelled) return
        setRuns((current) => mergeRun(current, nextRun))
        if (nextRun.status === "failed" && nextRun.error) {
          setRunError(friendlyRunError(nextRun.error))
        }
        if (nextMessages?.messages.length) {
          setMessages((current) =>
            mergeMessages(current, nextMessages.messages)
          )
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
      } finally {
        inFlight = false
      }
    }

    const interval = window.setInterval(poll, POLL_MS)
    void poll()
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [activeRunId, conversationId, handleAuthError])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = input.trim()
    if (!content || sending || starting) return

    setError(null)
    setRunError(null)
    setInput("")
    focusComposer()
    try {
      if (!conversationId) {
        const result = await startChat.mutateAsync({
          body: { content },
        })
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
      setMessages((current) => mergeMessages(current, [result.message]))
      setRuns((current) => mergeRun(current, result.run))
      window.dispatchEvent(new Event("taskraptor:chat-updated"))
      focusComposer()
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to send message"
      if (!handleAuthError(message)) setError(message)
      setInput((current) => (current.length > 0 ? current : content))
      focusComposer()
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
        <p className="text-sm text-muted-foreground">Loading chat...</p>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="mx-auto flex h-full min-h-0 w-full max-w-lg flex-col items-center justify-center gap-4 text-center">
        <IconAlertTriangle className="size-8 text-muted-foreground" />
        <div className="space-y-2">
          <h1 className="text-xl font-semibold tracking-tight">
            Conversation not found
          </h1>
          <p className="text-sm text-muted-foreground">
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
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border pb-4">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight">
            {conversationId
              ? conversationTitle(conversation)
              : "TaskRaptor chat"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {headerDescription}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => navigate("/")}
        >
          <IconMessagePlus />
          New Chat
        </Button>
      </header>

      <div className="scrollbar-subtle flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto overscroll-contain py-4">
        {messages.length === 0 ? (
          !conversationId ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-5 py-16">
              <p className="text-sm text-muted-foreground">
                What can I help you with?
              </p>
              <div className="grid w-full max-w-sm grid-cols-2 gap-2">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => {
                      setInput(prompt)
                      focusComposer()
                    }}
                    className="rounded-lg border border-border bg-card px-3 py-2.5 text-left text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-1 items-center justify-center py-16 text-center">
              <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
                No messages yet.
              </p>
            </div>
          )
        ) : (
          groupMessages(messages).map(({ message, isGroupStart }) => (
            <MessageBubble
              key={message.id}
              message={message}
              isGroupStart={isGroupStart}
            />
          ))
        )}
        {activeRun ? (
          <div className="flex justify-start">
            <div className="rounded-lg border border-border bg-muted px-4 py-3 text-sm text-muted-foreground">
              Thinking...
            </div>
          </div>
        ) : null}
        <div ref={scrollRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="shrink-0 border-t bg-background pt-4"
      >
        {error ? (
          <p className="mb-3 text-sm text-destructive">{error}</p>
        ) : null}
        {runError ? (
          <p className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
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
            aria-label="Message TaskRaptor"
            className="min-h-12 flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm leading-relaxed transition-[border-color,box-shadow] outline-none placeholder:text-muted-foreground focus-visible:ring-3 focus-visible:ring-ring focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!canSend}
            aria-label="Send message"
          >
            <IconSend />
          </Button>
        </div>
      </form>
    </div>
  )
}

function friendlyRunError(error: string): string {
  if (error === "quota_exceeded") {
    return "You've used up your message quota. Please upgrade or wait for it to reset."
  }
  if (error.includes("API key is missing") || error.includes("not active")) {
    return "I couldn't use your current AI model. Open Models, then add or update a provider key and make sure the model is active."
  }
  return "Something went wrong processing your message. Please try again."
}
