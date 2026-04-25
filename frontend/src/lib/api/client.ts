import createFetchClient, { type Middleware } from "openapi-fetch"
import createClient from "openapi-react-query"

import { getToken, NOT_FOUND_ERROR, SESSION_EXPIRED_ERROR } from "@/lib/auth"
import type { paths } from "@/lib/api/schema"

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const data = (await response.clone().json()) as { detail?: unknown }
    if (typeof data.detail === "string") return data.detail
  } catch {
    /* ignore */
  }
  return response.statusText || "Request failed"
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const token = getToken()
    if (!token) {
      throw new Error("Not authenticated")
    }
    request.headers.set("Authorization", `Bearer ${token}`)
    return request
  },
  async onResponse({ response }) {
    if (response.status === 401) {
      throw new Error(SESSION_EXPIRED_ERROR)
    }
    if (response.status === 404) {
      throw new Error(NOT_FOUND_ERROR)
    }
    if (!response.ok) {
      throw new Error(await parseErrorDetail(response))
    }
    return undefined
  },
}

export const fetchClient = createFetchClient<paths>({
  baseUrl: "",
})

fetchClient.use(authMiddleware)

export const $api = createClient(fetchClient)
