import { create } from 'zustand'
import { getCookie, setCookie, removeCookie } from '@/lib/cookies'

const AUTH_COOKIE = 'leanlens_auth'

interface AuthUser {
  id: number
  username: string
  email: string
}

interface Tokens {
  access: string
  refresh: string
}

interface AuthState {
  auth: {
    user: AuthUser | null
    setUser: (user: AuthUser | null) => void
    tokens: Tokens | null
    setTokens: (tokens: Tokens | null) => void
    reset: () => void
  }
}

interface Persisted {
  user: AuthUser | null
  tokens: Tokens | null
}

function readPersisted(): Persisted {
  try {
    const raw = getCookie(AUTH_COOKIE)
    if (!raw) return { user: null, tokens: null }
    return JSON.parse(raw) as Persisted
  } catch {
    return { user: null, tokens: null }
  }
}

function persist(next: Persisted) {
  if (next.user && next.tokens) {
    // 1-day refresh lifetime governs the session; keep the cookie 7 days (seconds)
    setCookie(AUTH_COOKIE, JSON.stringify(next), 7 * 24 * 60 * 60)
  } else {
    removeCookie(AUTH_COOKIE)
  }
}

export const useAuthStore = create<AuthState>()((set) => {
  const initial = readPersisted()
  return {
    auth: {
      user: initial.user,
      tokens: initial.tokens,
      setUser: (user) =>
        set((state) => {
          const next = { user, tokens: state.auth.tokens }
          persist(next)
          return { ...state, auth: { ...state.auth, user } }
        }),
      setTokens: (tokens) =>
        set((state) => {
          const next = { user: state.auth.user, tokens }
          persist(next)
          return { ...state, auth: { ...state.auth, tokens } }
        }),
      reset: () =>
        set((state) => {
          persist({ user: null, tokens: null })
          return { ...state, auth: { ...state.auth, user: null, tokens: null } }
        }),
    },
  }
})
