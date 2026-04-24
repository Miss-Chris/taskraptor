import { cn } from "@/lib/utils"

export function TaskTag({
  label,
  className,
}: {
  label: string
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border border-border bg-secondary/50 px-2 py-0.5 text-xs text-secondary-foreground",
        className,
      )}
    >
      {label}
    </span>
  )
}
