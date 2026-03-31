import { useAuthStore } from '@/stores/auth'

const BASE_URL = (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:8000/api/v1'

export class APIError extends Error {
  constructor(
    public readonly code: string,
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'APIError'
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  isFormData = false,
): Promise<T> {
  const token = useAuthStore.getState().accessToken
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!isFormData) headers['Content-Type'] = 'application/json'

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string> | undefined) },
  })

  if (!response.ok) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- external JSON shape
    const err = await response.json().catch(() => ({}) as any)
    throw new APIError(
      (err.detail?.code as string | undefined) ?? 'UNKNOWN',
      response.status,
      (err.detail?.message as string | undefined) ?? response.statusText,
    )
  }

  return response.json() as Promise<T>
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

export const api = {
  auth: {
    register: (email: string, password: string) =>
      request<{ access_token: string; refresh_token: string; tier: string; user_id: string }>(
        '/auth/register',
        { method: 'POST', body: JSON.stringify({ email, password }) },
      ),
    login: (email: string, password: string) =>
      request<{ access_token: string; refresh_token: string; tier: string; user_id: string }>(
        '/auth/login',
        { method: 'POST', body: JSON.stringify({ email, password }) },
      ),
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
  },
}
