import { useEffect, useState } from "react"
import { NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom"

import { DeleteConversationDialog } from "@/components/chat/DeleteConversationDialog"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { TelegramLinkPill } from "@/components/telegram/telegram-link-pill"
import { clearToken } from "@/lib/auth"
import { type ChatConversation } from "@/lib/chat"
import { useChatConversationsQuery } from "@/queries/chat"
import { useTaskFacetsQuery } from "@/queries/tasks"
import type { TaskFacets } from "@/lib/tasks"
import {
  IconCalendarEvent,
  IconChartBar,
  IconCheckbox,
  IconBug,
  IconLogout,
  IconMessages,
  IconMessagePlus,
  IconRobot,
  IconSettings,
  IconTag,
  IconTrash,
} from "@tabler/icons-react"

function getActiveConversationId(pathname: string): string | null {
  const match = pathname.match(/^\/c\/([^/]+)/)
  return match?.[1] ? decodeURIComponent(match[1]) : null
}

function getConversationLabel(conversation: ChatConversation): string {
  if (conversation.title.trim()) return conversation.title
  const latest = conversation.latest_message?.content.trim()
  if (latest) return latest
  return "New chat"
}

export function AppSidebar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [searchParams] = useSearchParams()
  const activeTag = searchParams.get("tag")

  const facetsQuery = useTaskFacetsQuery()
  const conversationsQuery = useChatConversationsQuery(6)
  const [tagsExpanded, setTagsExpanded] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ChatConversation | null>(null)

  const facets: TaskFacets | null = facetsQuery.data ?? null
  const conversations: ChatConversation[] = conversationsQuery.data?.conversations.slice(0, 5) ?? []
  const hasMoreConversations = (conversationsQuery.data?.count ?? 0) > 5
  const chatLoading = conversationsQuery.isLoading
  const chatLoadError = conversationsQuery.isError
    ? conversationsQuery.error instanceof Error
      ? conversationsQuery.error.message
      : "Could not load chats"
    : null
  const chatError = chatLoadError

  useEffect(() => {
    const err = facetsQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      clearToken()
      navigate("/login", { replace: true })
    }
  }, [facetsQuery.error, navigate])

  useEffect(() => {
    const err = conversationsQuery.error
    if (err instanceof Error && err.message === "SESSION_EXPIRED") {
      clearToken()
      navigate("/login", { replace: true })
    }
  }, [conversationsQuery.error, navigate])

  useEffect(() => {
    const handleChatUpdated = () => {
      void conversationsQuery.refetch()
    }
    window.addEventListener("taskraptor:chat-updated", handleChatUpdated)
    return () => {
      window.removeEventListener("taskraptor:chat-updated", handleChatUpdated)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- only refetch is required from useQuery
  }, [conversationsQuery.refetch])

  function handleLogout() {
    clearToken()
    navigate("/login", { replace: true })
  }

  function handleNewChat() {
    navigate("/")
  }

  const allTasksActive = pathname === "/tasks" && !activeTag
  const upcomingActive = pathname === "/tasks/upcoming"
  const conversationsActive = pathname === "/conversations"
  const activeConversationId = getActiveConversationId(pathname)
  const tagCounts = facets?.tag_counts ?? []
  const visibleTagCounts = tagCounts.slice(0, tagsExpanded ? 10 : 5)
  const canToggleTags = tagCounts.length > 5

  return (
    <Sidebar>
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-1">
          <span className="text-sidebar-foreground text-lg font-semibold tracking-tight">
            TaskRaptor
          </span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="py-2">
          <SidebarGroupLabel>Chat</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  type="button"
                  onClick={handleNewChat}
                  isActive={pathname === "/" && !activeConversationId}
                >
                  <IconMessagePlus />
                  <span>New Chat</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
            <SidebarMenu className="mt-0.5">
              {chatLoading ? (
                <SidebarMenuItem>
                  <SidebarMenuButton type="button" size="sm" className="text-muted-foreground">
                    <span className="truncate">Loading chats...</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ) : chatError ? (
                <SidebarMenuItem>
                  <SidebarMenuButton type="button" size="sm" className="text-destructive">
                    <span className="truncate">Could not load chats</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ) : conversations.length > 0 ? (
                conversations.map((conversation) => (
                  <SidebarMenuItem key={conversation.id}>
                    <SidebarMenuButton
                      asChild
                      size="sm"
                      className="pr-8"
                      isActive={activeConversationId === conversation.id}
                    >
                      <NavLink to={`/c/${conversation.id}`}>
                        <span className="truncate">{getConversationLabel(conversation)}</span>
                      </NavLink>
                    </SidebarMenuButton>
                    <SidebarMenuAction
                      type="button"
                      aria-label="Delete conversation"
                      onClick={() => setDeleteTarget(conversation)}
                    >
                      <IconTrash />
                    </SidebarMenuAction>
                  </SidebarMenuItem>
                ))
              ) : (
                <SidebarMenuItem>
                  <SidebarMenuButton type="button" size="sm" className="text-muted-foreground">
                    <span className="truncate">No conversations yet</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
              {hasMoreConversations ? (
                <SidebarMenuItem>
                  <SidebarMenuButton asChild size="sm" isActive={conversationsActive}>
                    <NavLink to="/conversations">
                      <IconMessages className="size-3.5" />
                      <span>All Conversations</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ) : null}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>Tasks</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={allTasksActive} tooltip="All tasks">
                  <NavLink to="/tasks">
                    <IconCheckbox />
                    <span>
                      All Tasks
                      {facets != null ? (
                        <span className="text-muted-foreground ml-1 font-normal">
                          ({facets.total})
                        </span>
                      ) : null}
                    </span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={upcomingActive} tooltip="Upcoming tasks">
                  <NavLink to="/tasks/upcoming">
                    <IconCalendarEvent />
                    <span>Upcoming tasks</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
            <p className="text-muted-foreground px-3 pt-3 text-xs font-medium">Tags</p>
            <SidebarMenu className="mt-1">
              {visibleTagCounts.length > 0 ? (
                visibleTagCounts.map((row) => {
                  const isTagActive = pathname === "/tasks" && activeTag === row.tag
                  return (
                    <SidebarMenuItem key={row.tag}>
                      <SidebarMenuButton asChild isActive={isTagActive} size="sm" className="pr-9">
                        <NavLink to={`/tasks?tag=${encodeURIComponent(row.tag)}`}>
                          <IconTag className="size-3.5" />
                          <span className="truncate">{row.tag}</span>
                        </NavLink>
                      </SidebarMenuButton>
                      <SidebarMenuBadge>{row.count}</SidebarMenuBadge>
                    </SidebarMenuItem>
                  )
                })
              ) : (
                <SidebarMenuItem>
                  <SidebarMenuButton type="button" size="sm" className="text-muted-foreground">
                    <span className="truncate">No tags yet</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
              {canToggleTags ? (
                <SidebarMenuItem>
                  <SidebarMenuButton
                    type="button"
                    size="sm"
                    className="text-muted-foreground"
                    onClick={() => setTagsExpanded((expanded) => !expanded)}
                  >
                    <span>{tagsExpanded ? "Show fewer" : "Show 5 more"}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ) : null}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>Automations</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton type="button">
                  <IconRobot />
                  <span>Automations</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>Account</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={pathname === "/debug"} tooltip="Agent debug">
                  <NavLink to="/debug">
                    <IconBug />
                    <span>Agent debug</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton type="button">
                  <IconChartBar />
                  <span>Usage / API key</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton type="button">
                  <IconSettings />
                  <span>Settings</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <div className="px-2 pb-2">
          <TelegramLinkPill />
        </div>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton type="button" onClick={handleLogout}>
              <IconLogout />
              <span>Log out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <DeleteConversationDialog
        conversation={deleteTarget}
        open={deleteTarget != null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        onDeleted={(conversationId) => {
          void conversationsQuery.refetch()
          if (conversationId === activeConversationId) {
            navigate("/", { replace: true })
          }
        }}
        onAuthExpired={() => navigate("/login", { replace: true })}
      />
    </Sidebar>
  )
}
