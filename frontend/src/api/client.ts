// The one fetch client for the VRMS API.
//
// - Same-origin requests (Vite proxies /api in development, Caddy in
//   production, D1), sent with credentials so the httpOnly refresh cookie
//   travels to the auth endpoints (D21).
// - Attaches the in-memory access token (never stored anywhere else).
// - On a 401, asks for one refresh and retries the request once; if the
//   refresh fails, the session is over.
// - Turns DRF errors into a typed ApiError with field and form-level messages.
// The server enforces every rule; client checks are for usability (CO-3).

import { getAccessToken } from '@/lib/session'

export interface DrfErrorBody {
  detail?: string | string[]
  code?: string
  non_field_errors?: string[]
  [field: string]: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | undefined
  readonly fieldErrors: Record<string, string[]>
  readonly nonFieldErrors: string[]
  readonly retryAfterSeconds: number | undefined
  /** The parsed response body, for callers that need more than the message. */
  readonly body: unknown

  constructor(
    status: number,
    message: string,
    options: {
      code?: string
      fieldErrors?: Record<string, string[]>
      nonFieldErrors?: string[]
      retryAfterSeconds?: number
      body?: unknown
    } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = options.code
    this.fieldErrors = options.fieldErrors ?? {}
    this.nonFieldErrors = options.nonFieldErrors ?? []
    this.retryAfterSeconds = options.retryAfterSeconds
    this.body = options.body
  }
}

const NETWORK_MESSAGE = 'We could not reach the server. Check your connection and try again.'

function toMessages(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(toMessages)
  if (value && typeof value === 'object') return Object.values(value).flatMap(toMessages)
  return []
}

export function parseApiError(status: number, body: unknown, retryAfter?: string | null) {
  const fieldErrors: Record<string, string[]> = {}
  let nonFieldErrors: string[] = []
  let detail: string | undefined
  let code: string | undefined

  if (body && typeof body === 'object' && !Array.isArray(body)) {
    for (const [key, value] of Object.entries(body as DrfErrorBody)) {
      if (key === 'detail') detail = toMessages(value).join(' ')
      else if (key === 'code' && typeof value === 'string') code = value
      else if (key === 'non_field_errors') nonFieldErrors = toMessages(value)
      else fieldErrors[key] = toMessages(value)
    }
  } else if (typeof body === 'string' && body.trim() && !body.trim().startsWith('<')) {
    detail = body.trim()
  }

  const firstField = Object.values(fieldErrors)[0]?.[0]
  const message =
    detail ?? nonFieldErrors[0] ?? firstField ?? `Something went wrong (error ${status}).`
  const seconds = retryAfter ? Number.parseInt(retryAfter, 10) : Number.NaN
  return new ApiError(status, message, {
    code,
    fieldErrors,
    nonFieldErrors: detail && !nonFieldErrors.length ? [] : nonFieldErrors,
    retryAfterSeconds: Number.isFinite(seconds) ? seconds : undefined,
    body,
  })
}

// ─── Session hooks (installed by the auth provider) ───────────────────────

interface SessionHooks {
  /** One refresh attempt; resolves true when a new access token is in memory. */
  refresh: () => Promise<boolean>
  /** The refresh failed: the session is over. */
  onSessionLost: () => void
}

let hooks: SessionHooks | null = null

export function installSessionHooks(next: SessionHooks | null): void {
  hooks = next
}

// ─── Requests ─────────────────────────────────────────────────────────────

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  /** A JSON body. */
  json?: unknown
  /** A multipart body (file uploads). */
  form?: FormData
  /** Send the access token and retry once after a refresh (default true). */
  auth?: boolean
  signal?: AbortSignal
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers = new Headers({ Accept: 'application/json' })
  let body: BodyInit | undefined
  if (options.form) {
    body = options.form
  } else if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(options.json)
  }
  const token = options.auth === false ? null : getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  try {
    return await fetch(new URL(path, window.location.origin), {
      method: options.method ?? (body ? 'POST' : 'GET'),
      headers,
      body,
      credentials: 'same-origin',
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, NETWORK_MESSAGE, { code: 'network_error' })
  }
}

async function readBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const type = response.headers.get('Content-Type') ?? ''
  if (type.includes('application/json')) return response.json()
  return response.text()
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options)

  if (response.status === 401 && options.auth !== false && hooks) {
    const refreshed = await hooks.refresh()
    if (!refreshed) {
      hooks.onSessionLost()
    } else {
      response = await send(path, options) // retried once, never more
    }
  }

  const body = await readBody(response)
  if (!response.ok) {
    throw parseApiError(response.status, body, response.headers.get('Retry-After'))
  }
  return body as T
}
