import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { AppShell } from "@/components/layout/AppShell"
import { AutomationsPage } from "@/pages/AutomationsPage"
import { ChatPage } from "@/pages/ChatPage"
import { ConversationsPage } from "@/pages/ConversationsPage"
import { DebugPage } from "@/pages/DebugPage"
import { LoginPage } from "@/pages/LoginPage"
import { ModelsPage } from "@/pages/ModelsPage"
import { RegisterPage } from "@/pages/RegisterPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { TaskDetailPage } from "@/pages/TaskDetailPage"
import { TasksPage } from "@/pages/TasksPage"
import { UpcomingTasksPage } from "@/pages/UpcomingTasksPage"

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<ChatPage />} />
          <Route path="automations" element={<AutomationsPage />} />
          <Route path="c/:conversationId" element={<ChatPage />} />
          <Route path="conversations" element={<ConversationsPage />} />
          <Route path="debug" element={<DebugPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="tasks/upcoming" element={<UpcomingTasksPage />} />
          <Route path="tasks/:taskId" element={<TaskDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
