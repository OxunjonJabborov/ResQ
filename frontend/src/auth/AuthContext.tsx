import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from 'react'

import { tokens } from '../api/client'
import { authApi } from '../api/endpoints'
import type { AuthResponse, User } from '../api/types'
import i18n from '../i18n'

interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (res: AuthResponse) => void
  logout: () => Promise<void>
  refetchUser: () => Promise<unknown>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const access = useSyncExternalStore(
    (cb) => tokens.subscribe(cb),
    () => tokens.access,
  )

  const meQuery = useQuery({
    queryKey: ['me'],
    queryFn: authApi.me,
    enabled: !!access,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  const login = useCallback(
    (res: AuthResponse) => {
      tokens.set(res.access, res.refresh)
      queryClient.setQueryData(['me'], res.user)
      void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    const refresh = tokens.refresh
    try {
      if (refresh) await authApi.logout(refresh)
    } catch {
      /* token already invalid: still log out locally */
    }
    tokens.clear()
    queryClient.clear()
  }, [queryClient])

  // Keep the UI language in sync with the account preference after login.
  const user = access ? (meQuery.data ?? null) : null
  useEffect(() => {
    if (user?.language && user.language !== i18n.language) void i18n.changeLanguage(user.language)
  }, [user?.language])

  const value = useMemo<AuthState>(
    () => ({
      user,
      isLoading: !!access && meQuery.isPending,
      isAuthenticated: !!user,
      login,
      logout,
      refetchUser: meQuery.refetch,
    }),
    [user, access, meQuery.isPending, meQuery.refetch, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
