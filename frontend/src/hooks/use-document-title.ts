import { useEffect } from "react"

const APP_TITLE = "TaskRaptor"

export function formatDocumentTitle(title?: string): string {
  const pageTitle = title?.trim()
  return pageTitle ? `${pageTitle} | ${APP_TITLE}` : APP_TITLE
}

export function useDocumentTitle(title?: string) {
  useEffect(() => {
    document.title = formatDocumentTitle(title)
  }, [title])
}
