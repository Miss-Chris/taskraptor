/**
 * Read the CSRF token Django sets in the csrftoken cookie.
 * CSRF_COOKIE_HTTPONLY must be False for this to work.
 */
function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function isSafeMethod(method?: string): boolean {
  const normalized = method?.toUpperCase() ?? "GET";
  return ["GET", "HEAD", "OPTIONS", "TRACE"].includes(normalized);
}

async function ensureCsrfCookie(): Promise<void> {
  if (getCsrfToken()) return;

  await fetch("/api/auth/csrf", {
    credentials: "include",
  });
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (!isSafeMethod(options.method)) {
    await ensureCsrfCookie();
  }

  const res = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
      ...(options.headers as Record<string, string>),
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body?.detail ?? "Request failed");
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
