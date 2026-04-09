import type { ReactNode } from "react"

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-muted/40 p-6">
      <div className="w-full max-w-sm">{children}</div>
    </div>
  )
}
