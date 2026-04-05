import { useAuthStore } from '@/stores/auth'

const BASE_URL = (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:8000/api/v1'

export class APIError extends Error {
  constructor(
    public readonly code: string,
    public readonly status: number,
    message: string,
    public readonly retryAfterSeconds?: number,
  ) {
    super(message)
    this.name = 'APIError'
  }
}

export class RateLimitError extends APIError {
  constructor(status: number, message: string, retryAfterSeconds: number) {
    super('RAIN-E429', status, message, retryAfterSeconds)
    this.name = 'RateLimitError'
  }
}

interface AuthResponse {
  access_token: string
  refresh_token: string
  tier: string
  user_id: string
}

// Single-flight refresh: share one in-progress refresh across concurrent 401s
let refreshInFlight: Promise<AuthResponse | null> | null = null

async function callRefresh(): Promise<AuthResponse | null> {
  try {
    const response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
    if (!response.ok) return null
    return (await response.json()) as AuthResponse
  } catch {
    return null
  }
}

async function refreshAccessToken(): Promise<AuthResponse | null> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = callRefresh().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  isFormData = false,
  _retried = false,
): Promise<T> {
  const token = useAuthStore.getState().accessToken
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!isFormData) headers['Content-Type'] = 'application/json'

  const response = await fetch(`${BASE_URL}${path}`, {
    credentials: 'include', // send httpOnly refresh cookie to /auth/refresh and /auth/logout
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string> | undefined) },
  })

  if (response.ok) {
    // 204 No Content → return null-like
    if (response.status === 204) return undefined as unknown as T
    return response.json() as Promise<T>
  }

  // 429 Too Many Requests — surface as RateLimitError with Retry-After
  if (response.status === 429) {
    const retryAfter = Number(response.headers.get('Retry-After') ?? '60')
    throw new RateLimitError(429, 'Rate limit exceeded — slow down', Number.isFinite(retryAfter) ? retryAfter : 60)
  }

  // 401 → try refresh once, then replay the original request
  if (response.status === 401 && !_retried && !path.startsWith('/auth/')) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      useAuthStore.getState().setAccessToken(refreshed.access_token, refreshed.tier)
      return request<T>(path, options, isFormData, true)
    }
    // refresh failed — clear auth so UI can redirect to /login
    useAuthStore.getState().clearAuth()
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- external JSON shape
  const err = await response.json().catch(() => ({}) as any)
  throw new APIError(
    (err.detail?.code as string | undefined) ?? 'UNKNOWN',
    response.status,
    (err.detail?.message as string | undefined) ?? response.statusText,
  )
}

export const api = {
  auth: {
    register: (email: string, password: string) =>
      request<AuthResponse>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    login: (email: string, password: string) =>
      request<AuthResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    refresh: () => request<AuthResponse>('/auth/refresh', { method: 'POST', body: '{}' }),
    logout: () => request<void>('/auth/logout', { method: 'POST' }),
  },
  sessions: {
    create: (file: File, params: Record<string, unknown>) => {
      const fd = new FormData()
      fd.append('file', file)
      Object.entries(params).forEach(([k, v]) => fd.append(k, String(v)))
      return request<{ id: string; status: string }>('/sessions/', { method: 'POST', body: fd }, true)
    },
    get: (id: string) => request<{ id: string; status: string; output_lufs?: number }>(`/sessions/${id}`),
    download: (id: string) => `/api/v1/sessions/${id}/download`,
  },
}
