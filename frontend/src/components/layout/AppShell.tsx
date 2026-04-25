import { Outlet } from "react-router-dom"

import { AppSidebar } from "@/components/layout/app-sidebar"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

export function AppShell() {
  return (
    <SidebarProvider className="h-svh min-h-0 overflow-hidden">
      <AppSidebar />
      <SidebarInset>
        <div className="flex min-h-0 flex-1 flex-col overflow-auto p-4 md:p-6">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
