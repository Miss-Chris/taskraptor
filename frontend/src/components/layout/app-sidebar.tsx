import { useCallback, useEffect, useState } from "react"
import { NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { TelegramLinkPill } from "@/components/telegram/telegram-link-pill"
import { clearToken } from "@/lib/auth"
import { fetchTaskFacets, type TaskFacets } from "@/lib/tasks"
import {
  IconCalendarEvent,
  IconChartBar,
  IconCheckbox,
  IconBug,
  IconLogout,
  IconMessagePlus,
  IconRobot,
  IconSettings,
  IconTag,
} from "@tabler/icons-react"

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Done",
  cancelled: "Cancelled",
}

function formatStatusSummary(facets: TaskFacets): string {
  return facets.status_counts
    .map((row) => `${STATUS_LABEL[row.status] ?? row.status}: ${row.count}`)
    .join(" · ")
}

export function AppSidebar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [searchParams] = useSearchParams()
  const activeTag = searchParams.get("tag")

  const [facets, setFacets] = useState<TaskFacets | null>(null)

  const loadFacets = useCallback(async () => {
    try {
      const data = await fetchTaskFacets()
      setFacets(data)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load task summary"
      if (msg === "SESSION_EXPIRED") {
        clearToken()
        navigate("/login", { replace: true })
        return
      }
      setFacets(null)
    }
  }, [navigate])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      await loadFacets()
      if (cancelled) return
    })()
    return () => {
      cancelled = true
    }
  }, [loadFacets])

  function handleLogout() {
    clearToken()
    navigate("/login", { replace: true })
  }

  const allTasksActive = pathname === "/tasks" && !activeTag
  const upcomingActive = pathname === "/tasks/upcoming"

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
        <SidebarGroup>
          <SidebarGroupLabel>Chat</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton type="button">
                  <IconMessagePlus />
                  <span>New Chat</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
            <p className="text-muted-foreground px-3 pt-2 text-xs font-medium">
              Recent conversations
            </p>
            <SidebarMenu className="mt-1">
              <SidebarMenuItem>
                <SidebarMenuButton type="button" size="sm" className="text-muted-foreground">
                  <span className="truncate">No conversations yet</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
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
            {facets != null && facets.status_counts.length > 0 ? (
              <p className="text-muted-foreground px-3 pt-2 text-xs leading-snug">
                {formatStatusSummary(facets)}
              </p>
            ) : null}
            <p className="text-muted-foreground px-3 pt-3 text-xs font-medium">Tags</p>
            <SidebarMenu className="mt-1">
              {facets != null && facets.tag_counts.length > 0 ? (
                facets.tag_counts.map((row) => {
                  const isTagActive = pathname === "/tasks" && activeTag === row.tag
                  return (
                    <SidebarMenuItem key={row.tag}>
                      <SidebarMenuButton asChild isActive={isTagActive} size="sm">
                        <NavLink to={`/tasks?tag=${encodeURIComponent(row.tag)}`}>
                          <IconTag className="size-3.5" />
                          <span>
                            {row.tag}
                            <span className="text-muted-foreground ml-1 font-normal">
                              ({row.count})
                            </span>
                          </span>
                        </NavLink>
                      </SidebarMenuButton>
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
    </Sidebar>
  )
}
