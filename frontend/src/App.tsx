import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { AppShell } from "@/components/layout/AppShell"
import { DebugPage } from "@/pages/DebugPage"
import { HomePage } from "@/pages/HomePage"
import { LoginPage } from "@/pages/LoginPage"
import { RegisterPage } from "@/pages/RegisterPage"
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
          <Route index element={<HomePage />} />
          <Route path="debug" element={<DebugPage />} />
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
