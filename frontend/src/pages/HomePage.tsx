import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
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

  function handleLogout() {
    clearToken()
    navigate("/login", { replace: true })
  }

  if (loading) {
    return (
      <div className="flex min-h-svh items-center justify-center p-6">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </div>
    )
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Welcome</CardTitle>
          <CardDescription>
            Signed in as <span className="text-foreground font-medium">{me?.email}</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm leading-relaxed">
          <p>You&apos;re connected to TaskRaptor. Build out your dashboard here.</p>
          <p className="mt-2 font-mono text-xs">
            (Press <kbd className="rounded border px-1">d</kbd> to toggle dark mode)
          </p>
        </CardContent>
        <CardFooter>
          <Button type="button" variant="outline" onClick={handleLogout}>
            Log out
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
