import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios'
import { useAuthStore } from '@/stores/auth-store'

/**
 * LeanLens API client.
 *
 * - Base `/api` (same origin behind nginx in prod; Vite dev proxy in dev)
 * - `Authorization: JWT <access>` (upstream SIMPLE_JWT config uses "JWT", not "Bearer")
 * - One automatic refresh-and-retry on 401; hard logout if refresh fails
 */

export const api = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const tokens = useAuthStore.getState().auth.tokens
  if (tokens?.access) {
    config.headers.Authorization = `JWT ${tokens.access}`
  }
  return config
})

let refreshing: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const { auth } = useAuthStore.getState()
  if (!auth.tokens?.refresh) return null
  try {
    const { data } = await axios.post<{ access: string; refresh?: string }>(
      '/api/auth/jwt/refresh/',
      { refresh: auth.tokens.refresh },
      { timeout: 15_000 }
    )
    const access = data.access
    const refresh = data.refresh ?? auth.tokens.refresh
    auth.setTokens({ access, refresh })
    return access
  } catch {
    auth.reset()
    return null
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined
    const status = error.response?.status
    const isAuthCall = typeof config?.url === 'string' && config.url.includes('/auth/jwt/')

    if (status === 401 && config && !config._retried && !isAuthCall) {
      config._retried = true
      refreshing = refreshing ?? refreshAccessToken()
      const access = await refreshing
      refreshing = null
      if (access) {
        config.headers = { ...config.headers, Authorization: `JWT ${access}` }
        return api.request(config)
      }
      // refresh failed -> session over
      useAuthStore.getState().auth.reset()
      if (typeof window !== 'undefined') {
        window.location.href = '/sign-in'
      }
    }
    return Promise.reject(error)
  }
)

/** Human-readable message for toasts. */
export function apiErrorMessage(error: unknown, fallback = 'Request failed'): string {
  if (axios.isAxiosError(error)) {
    const data: unknown = error.response?.data
    if (data && typeof data === 'object') {
      const record = data as Record<string, unknown>
      for (const key of ['detail', 'message', 'error']) {
        const value = record[key]
        if (typeof value === 'string' && value) return value
      }
      // DRF field errors: {field: ["msg"]}
      const first = Object.values(record).flat(2)[0]
      if (typeof first === 'string' && first) return first
    }
    if (error.code === 'ECONNABORTED') return 'The server took too long to respond.'
  }
  return fallback
}
