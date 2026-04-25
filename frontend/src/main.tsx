import { StrictMode } from "react"
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import * as Sentry from "@sentry/react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { TooltipProvider } from "@/components/ui/tooltip"
import { endSession, isAuthError } from "@/lib/auth"

const sentryDsn = import.meta.env.VITE_SENTRY_DSN

if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    sendDefaultPii: import.meta.env.VITE_SENTRY_SEND_DEFAULT_PII !== "false",
  })
}

let redirectingForAuth = false

function handleGlobalError(error: unknown) {
  if (!isAuthError(error)) return

  endSession(queryClient)
  if (redirectingForAuth || window.location.pathname === "/login") return

  redirectingForAuth = true
  window.location.assign("/login")
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: handleGlobalError,
  }),
  mutationCache: new MutationCache({
    onError: handleGlobalError,
  }),
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
          <App />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>
)
