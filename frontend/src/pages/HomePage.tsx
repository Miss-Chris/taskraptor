import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { clearToken, fetchMe, type MeResponse } from "@/lib/auth"

export function HomePage() {
  const navigate = useNavigate()
  const [me, setMe] = useState<MeResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const user = await fetchMe()
        if (!cancelled) setMe(user)
      } catch {
        clearToken()
        navigate("/login", { replace: true })
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [navigate])

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-12">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-lg">
      <Card>
        <CardHeader>
          <CardTitle>Home</CardTitle>
          <CardDescription>
            Signed in as <span className="text-foreground font-medium">{me?.email}</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm leading-relaxed">
          <p>Placeholder home. Chat, tasks, and more will show up here.</p>
          <p className="mt-2 font-mono text-xs">
            (Press <kbd className="rounded border px-1">d</kbd> to toggle dark mode)
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
