/**
 * Thin fetch wrapper: JSON in/out, JWT bearer auth with a single-flight refresh on 401,
 * Accept-Language from the active UI language, and typed errors.
 */
import i18n from '../i18n'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1'
const ACCESS_KEY = 'resq.access'
const REFRESH_KEY = 'resq.refresh'

export class ApiError extends Error {
  status: number
  code?: string
  data: Record<string, unknown>

  constructor(status: number, data: Record<string, unknown>) {
    super(ApiError.messageFrom(data) || `HTTP ${status}`)
    this.status = status
    this.code = typeof data.code === 'string' ? data.code : undefined
    this.data = data
  }

  /** Field-level validation errors from DRF: { field: ["message"] }. */
  get fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {}
    for (const [key, value] of Object.entries(this.data)) {
      if (Array.isArray(value) && typeof value[0] === 'string') out[key] = value[0]
    }
    return out
  }

  static messageFrom(data: Record<string, unknown>): string {
    if (typeof data.detail === 'string') return data.detail
    for (const value of Object.values(data)) {
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    }
    return ''
  }
}

type Listener = () => void
const listeners = new Set<Listener>()

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* storage unavailable (private mode): tokens live for this tab only */
  }
}

let accessToken = safeGet(ACCESS_KEY)
let refreshToken = safeGet(REFRESH_KEY)

export const tokens = {
  get access() {
    return accessToken
  },
  get refresh() {
    return refreshToken
  },
  set(access: string | null, refresh: string | null) {
    accessToken = access
    refreshToken = refresh
    safeSet(ACCESS_KEY, access)
    safeSet(REFRESH_KEY, refresh)
    listeners.forEach((fn) => fn())
  },
  clear() {
    this.set(null, null)
  },
  subscribe(fn: Listener) {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },
}

let refreshing: Promise<boolean> | null = null

async function refreshAccess(): Promise<boolean> {
  if (!refreshToken) return false
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/token/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: refreshToken }),
      })
      if (!res.ok) {
        tokens.clear()
        return false
      }
      const data = (await res.json()) as { access: string; refresh?: string }
      tokens.set(data.access, data.refresh ?? refreshToken)
      return true
    } catch {
      return false
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

export interface RequestOptions {
  method?: string
  body?: unknown
  params?: Record<string, string | number | boolean | undefined | null>
  signal?: AbortSignal
}

function buildUrl(path: string, params?: RequestOptions['params']) {
  const url = new URL(path.startsWith('http') ? path : `${API_BASE}${path}`, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

export async function api<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = { 'Accept-Language': i18n.language || 'uz' }
  let body: BodyInit | undefined
  if (opts.body instanceof FormData) {
    body = opts.body
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`

  const res = await fetch(buildUrl(path, opts.params), {
    method: opts.method ?? (body ? 'POST' : 'GET'),
    headers,
    body,
    signal: opts.signal,
  })

  if (res.status === 401 && !retried && refreshToken) {
    if (await refreshAccess()) return api<T>(path, opts, true)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  const data = text ? (JSON.parse(text) as unknown) : null
  if (!res.ok) {
    throw new ApiError(res.status, (data && typeof data === 'object' ? data : {}) as Record<string, unknown>)
  }
  return data as T
}
