/**
 * API client. The access token lives only in this module's memory, never in localStorage. The
 * refresh token is an HttpOnly cookie that JavaScript cannot read.
 */
import type { AuthResponse } from "@/lib/types"

const API_URL: string = import.meta.env.VITE_API_URL
if (!API_URL) throw new Error("VITE_API_URL is not configured.")

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: { field: string; message: string }[]

  constructor(status: number, code: string, message: string, details: { field: string; message: string }[] = []) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let accessToken: string | null = null
let refreshInFlight: Promise<AuthResponse | null> | null = null
let onSessionExpired: () => void = () => {}

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler
}

type Query = Record<string, string | number | undefined | null>

function buildUrl(path: string, query?: Query) {
  const url = new URL(API_URL + path)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value))
  }
  return url
}

async function send(method: string, path: string, body?: unknown, query?: Query) {
  return fetch(buildUrl(path, query), {
    method,
    credentials: "include",
    headers: {
      "X-Requested-With": "starter-app",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}

async function toError(response: Response) {
  try {
    const { error } = await response.json()
    return new ApiError(response.status, error.code, error.message, error.details)
  } catch {
    return new ApiError(response.status, "unknown_error", "The request failed.")
  }
}

async function callRefresh(): Promise<AuthResponse | null> {
  const attempt = async (): Promise<AuthResponse | null> => {
    for (let tries = 0; tries < 3; tries += 1) {
      const response = await fetch(buildUrl("/auth/refresh"), {
        method: "POST",
        credentials: "include",
        headers: { "X-Requested-With": "starter-app" },
      })
      if (response.ok) {
        const data: AuthResponse = await response.json()
        setAccessToken(data.access_token)
        return data
      }
      // Another tab rotated the token just now. Its new cookie will be picked up on retry.
      if (response.status !== 409) return null
      await new Promise((resolve) => setTimeout(resolve, 400))
    }
    return null
  }
  // Serializes refreshes across tabs, which share the cookie.
  return navigator.locks ? navigator.locks.request("admin-session-refresh", attempt) : attempt()
}

/** Exchange the refresh cookie for new credentials. Concurrent callers share one request. */
export function refreshSession(): Promise<AuthResponse | null> {
  refreshInFlight ??= callRefresh().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  let response = await send(method, path, body, query)
  if (response.status === 401) {
    const error = await toError(response.clone())
    // Only an expired session triggers a refresh, not a wrong password or MFA challenge.
    if (error.code === "authentication_required") {
      if (await refreshSession()) {
        response = await send(method, path, body, query)
      } else {
        setAccessToken(null)
        onSessionExpired()
      }
    }
  }
  if (!response.ok) throw await toError(response)
  if (response.status === 204) return undefined as T
  return response.json()
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, undefined, query),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.details?.[0]
    return detail ? `${detail.field}: ${detail.message}` : error.message
  }
  return "Could not reach the server. Please try again."
}
