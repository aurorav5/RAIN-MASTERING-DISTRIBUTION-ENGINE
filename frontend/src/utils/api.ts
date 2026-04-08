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

export interface AnalysisData {
  input_lufs: number
  input_true_peak: number
  spectral_centroid: number
  crest_factor: number
  stereo_width: number
  bass_energy_ratio: number
  dynamic_range: number
  sample_rate: number
  channels: number
  duration: number
  output_lufs: number | null
  output_true_peak: number | null
  output_dynamic_range: number | null
  output_stereo_width: number | null
  output_spectral_centroid: number | null
}

export interface ProcessResult {
  session_id: string
  status: string
  output_lufs: number
  output_true_peak: number
  output_dynamic_range: number
  output_stereo_width: number
  output_spectral_centroid: number
}

function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
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
  master: {
    upload: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return request<{ session_id: string; filename: string; format: string; file_size: number; duration: number | null }>(
        '/master/upload', { method: 'POST', body: fd }, true,
      )
    },
    analysis: (sessionId: string) =>
      request<AnalysisData>(`/master/${sessionId}/analysis`),
    process: (sessionId: string, params: Record<string, unknown>) =>
      request<ProcessResult>(
        `/master/${sessionId}/process`,
        { method: 'POST', body: JSON.stringify(params) },
      ),
    downloadUrl: (sessionId: string, format: 'wav' | 'mp3') =>
      `${BASE_URL}/master/${sessionId}/download/${format}`,
    features: (sessionId: string) =>
      request<Record<string, number>>(`/master/${sessionId}/features`),
    qcReport: (sessionId: string) =>
      request<QCReportData>(`/master/${sessionId}/qc`),
  },
  separate: {
    upload: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return request<{ job_id?: string; status: string; filename?: string; reason?: string; message?: string }>(
        '/separate/upload', { method: 'POST', body: fd }, true,
      )
    },
    status: (jobId: string) =>
      request<{ job_id: string; status: string; progress: number; stems: Record<string, { status: string }>; error: string | null }>(
        `/separate/${jobId}/status`,
      ),
    stems: (jobId: string) =>
      request<{ job_id: string; status: string; stems: Array<{ name: string; status: string; download_url: string | null }> }>(
        `/separate/${jobId}/stems`,
      ),
  },
  qc: {
    platforms: () => request<PlatformTargetData[]>('/qc/platforms'),
  },
  billing: {
    async checkoutSession(priceId: string): Promise<{ url: string; session_id: string }> {
      return post('/billing/checkout-session', {
        price_id: priceId,
        success_url: window.location.origin + '/app?upgraded=true',
        cancel_url: window.location.origin + '/?checkout=canceled',
      })
    },
    async subscription(): Promise<{ tier: string; status: string; current_period_end: string | null; cancel_at_period_end: boolean }> {
      return get('/billing/subscription')
    },
    async portalSession(): Promise<{ url: string }> {
      return post('/billing/portal-session', {
        return_url: window.location.origin + '/app/settings',
      })
    },
  },
  waitlist: {
    async join(email: string, referralCode?: string): Promise<{ joined: boolean; position: number }> {
      return post('/waitlist/join', { email, referral_code: referralCode ?? null })
    },
    async count(): Promise<{ count: number }> {
      return get('/waitlist/count')
    },
  },
}

export interface PlatformTargetData {
  slug: string
  name: string
  target_lufs: number
  true_peak_ceiling: number
  lra_min: number | null
  lra_max: number | null
  notes: string
}

export interface QCCheckData {
  id: number
  name: string
  severity: string
  passed: boolean
  value: number | null
  threshold: number | null
  auto_remediated: boolean
  detail: string
}

export interface QCReportData {
  platform: string
  passed: boolean
  critical_failures: number
  remediated_count: number
  checks: QCCheckData[]
}
